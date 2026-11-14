"""Conservative, non-executing repair for one known generated-code pattern."""
import argparse, ast, datetime, json, pathlib, shutil, sys
ROOT=pathlib.Path(__file__).resolve().parent

def repair(source):
    tree=ast.parse(source)
    lines=source.splitlines(keepends=True)
    changes=[]
    for node in ast.walk(tree):
        if not isinstance(node,ast.Expr) or not isinstance(node.value,ast.Call): continue
        call=node.value
        if not (isinstance(call.func,ast.Attribute) and call.func.attr=='system' and isinstance(call.func.value,ast.Name) and call.func.value.id=='os'): continue
        if len(call.args)!=1 or call.keywords: continue
        arg=call.args[0]
        if not isinstance(arg,ast.IfExp): continue
        if not (isinstance(arg.body,ast.Constant) and arg.body.value=='cls' and isinstance(arg.orelse,ast.Constant) and arg.orelse.value=='clear'): continue
        if not (isinstance(arg.test,ast.Compare) and isinstance(arg.test.left,ast.Attribute) and isinstance(arg.test.left.value,ast.Name) and arg.test.left.value.id=='os' and arg.test.left.attr=='name'): continue
        if not (len(arg.test.ops)==1 and isinstance(arg.test.ops[0],ast.Eq) and len(arg.test.comparators)==1 and isinstance(arg.test.comparators[0],ast.Constant) and arg.test.comparators[0].value=='nt'): continue
        if node.lineno != node.end_lineno: continue
        line=lines[node.lineno-1]
        if line.strip().startswith('os.system('):
            indent=line[:len(line)-len(line.lstrip())]
            lines[node.lineno-1]=indent+'pass  # Ekran temizleme komutu guvenlik icin kaldirildi\n'
            changes.append({'line':node.lineno,'action':'remove_known_console_clear'})
    return ''.join(lines),changes

def main():
    p=argparse.ArgumentParser();p.add_argument('job_dir');p.add_argument('--report-dir');a=p.parse_args()
    job=pathlib.Path(a.job_dir).resolve()
    sourcefile=job/'uygulama.py'
    if not sourcefile.is_file():p.error('uygulama.py bulunamadi')
    source=sourcefile.read_text(encoding='utf-8-sig')
    fixed,changes=repair(source)
    if not changes:
        print('Bilinen guvenli duzeltme kalibi bulunamadi. Orijinal degistirilmedi.');return 2
    dest=job.parent/(job.name+'_DUZELTME_ADAYI')
    if dest.exists():
        dest=job.parent/(job.name+'_DUZELTME_ADAYI_'+datetime.datetime.now().strftime('%H%M%S'))
    dest.mkdir(parents=True)
    (dest/'uygulama.py').write_text(fixed,encoding='utf-8')
    (dest/'DUZELTME_RAPORU.json').write_text(json.dumps({'changes':changes,'original':str(sourcefile),'note':'Kod calistirilmadi; davranis testi yapilmadi'},ensure_ascii=False,indent=2),encoding='utf-8')
    sys.path.insert(0,str(ROOT))
    try:
        from kado_entegre_denetim import check
        result=check(dest)
    except Exception as e:
        print('Denetim hatasi:',repr(e));return 3
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if a.report_dir:
        reportdir=pathlib.Path(a.report_dir);reportdir.mkdir(parents=True,exist_ok=True)
        (reportdir/(dest.name+'_denetim.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('DUZELTME ADAYI:',dest)
    return 0 if result['karar']=='STATIK_KONTROL_GECTI_TEST_GEREKLI' else 1
if __name__=='__main__':sys.exit(main())
