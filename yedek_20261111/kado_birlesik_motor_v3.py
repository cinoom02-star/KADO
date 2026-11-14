"""KADO V3: one production attempt, one bounded repair, static audit, safe arithmetic behavior probe.
Does NOT execute generated Python, publish, or touch production WhatsApp.
"""
import ast, importlib.util, json, pathlib, sys, time, traceback, operator
ROOT=pathlib.Path(__file__).resolve().parent
MOTOR_DIR=ROOT/'kado_agent_motor'; REPORT_DIR=ROOT/'entegrasyon_raporlari'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError('Modul bulunamadi: '+str(path))
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod

OPS={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod}
def evaluate(node,env,depth=0):
    if depth>12:raise ValueError('derinlik siniri')
    if isinstance(node,ast.Constant) and type(node.value) in (int,float):return node.value
    if isinstance(node,ast.Name) and node.id in env:return env[node.id]
    if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
        v=evaluate(node.operand,env,depth+1);return v if isinstance(node.op,ast.UAdd) else -v
    if isinstance(node,ast.BinOp) and type(node.op) in OPS:
        a=evaluate(node.left,env,depth+1);b=evaluate(node.right,env,depth+1)
        if abs(a)>1e8 or abs(b)>1e8:raise ValueError('sayi siniri')
        return OPS[type(node.op)](a,b)
    raise ValueError('desteklenmeyen ifade')

def behavior_probe(source,goal):
    """Conservative AST interpreter: only 2-arg pure arithmetic functions; no code execution."""
    result={'durum':'KAPSAM_DISI','testler':[],'aciklama':'Uretilen Python calistirilmadi; yalnizca izinli AST aritmetigi yorumlandi.'}
    low=goal.casefold()
    if 'topla' in low or 'toplam' in low: expected=lambda a,b:a+b
    elif 'cikar' in low or 'çıkar' in low or 'fark' in low:expected=lambda a,b:a-b
    elif 'carp' in low or 'çarp' in low:expected=lambda a,b:a*b
    else:return result
    try:tree=ast.parse(source)
    except SyntaxError:return {**result,'durum':'SOZDIZIMI_HATASI'}
    funcs=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
    for f in funcs:
        if isinstance(f,ast.AsyncFunctionDef) or len(f.args.args)!=2 or f.args.vararg or f.args.kwarg or f.args.defaults or f.decorator_list:continue
        if len(f.body)!=1 or not isinstance(f.body[0],ast.Return):continue
        names=[a.arg for a in f.args.args]
        if not all(n.isidentifier() for n in names):continue
        cases=[(2,3),(0,7),(-4,6)]
        try:
            for a,b in cases:
                got=evaluate(f.body[0].value,{names[0]:a,names[1]:b})
                exp=expected(a,b)
                ok=type(got) in (int,float) and abs(got-exp)<1e-9
                result['testler'].append({'girdi':[a,b],'beklenen':exp,'bulunan':got,'gecti':ok})
            result['fonksiyon']=f.name
            result['durum']='GECTI' if all(t['gecti'] for t in result['testler']) else 'KALDI'
            return result
        except (ValueError,ZeroDivisionError,OverflowError,TypeError):
            result['testler']=[]
    return result

def main():
    sys.path.insert(0,str(ROOT))
    motor=load('kado_motor',MOTOR_DIR/'kado_motor.py')
    flow=load('kado_uzman_akis_v1',ROOT/'kado_uzman_akis_v1.py')
    if not hasattr(motor,'QualityRejected') or not hasattr(motor,'code_issues'):raise RuntimeError('Kalite V2 motoru eksik')
    original=motor.execute
    def execute(job):
        if job['kind']!='kod':return original(job)
        jid=job['id'];dest=motor.OUT/jid;dest.mkdir(parents=True,exist_ok=True)
        motor.log('start',id=jid,kind='kod',mode='v3_audit_behavior_repair')
        prompt=('Python 3 icin tek dosya uret. Sadece ```python kod blogu. '
                'os, subprocess, ag, dosya islemleri, harici kutuphane kullanma. '
                'Basit aritmetik gorevde iki parametreli saf fonksiyon kullan. Gorev: '+job['goal'])
        raw=motor.ask_model(prompt)
        (dest/'deneme_1.txt').write_text(raw,encoding='utf-8')
        code=motor.extract_code(raw)
        def valid(c):
            try:ast.parse(c);return True
            except SyntaxError:return False
        repaired=False
        if not valid(code):
            motor.log('syntax_repair_requested',id=jid)
            repair_prompt=('Asagidaki Python kodunda SOZDIZIMI hatasi var. Goreve uygun, '
                           'tek dosya, sadece ```python kod blogu olarak duzelt. '
                           'os, subprocess, ag ve dosya islemleri kullanma. Gorev: '+job['goal']+'\nKod:\n'+code[:5000])
            raw2=motor.ask_model(repair_prompt)
            (dest/'duzeltme_deneme_1.txt').write_text(raw2,encoding='utf-8')
            candidate=motor.extract_code(raw2)
            if valid(candidate):code=candidate;repaired=True
        if not valid(code):
            (dest/'SONUC.json').write_text(json.dumps({'karar':'SOZDIZIMI_HATASI_INCELEME','otomatik_duzeltme':False},ensure_ascii=False,indent=2),encoding='utf-8')
            raise motor.QualityRejected('Iki denemede de sozdizimi hatasi; inceleme gerekli')
        (dest/'uygulama.py').write_text(code+'\n',encoding='utf-8')
        issues=motor.code_issues(code)
        REPORT_DIR.mkdir(parents=True,exist_ok=True)
        try:
            flow.run(dest,REPORT_DIR)
            report_path=REPORT_DIR/(jid+'_uzman_akis.json')
            report=json.loads(report_path.read_text(encoding='utf-8'))
        except Exception as exc:
            (dest/'DENETIM_HATASI.txt').write_text(repr(exc),encoding='utf-8')
            raise motor.QualityRejected('Uzman denetimi basarisiz: '+str(exc)[:150]) from exc
        candidate=report.get('candidate')
        audit_source=pathlib.Path(candidate).read_text(encoding='utf-8') if candidate else code
        # Never behavior-probe code with unresolved static issues.
        behavior=(behavior_probe(audit_source,job['goal']) if report['decision']=='STATIK_KONTROL_GECTI_DAVRANIS_TESTI_GEREKLI'
                  else {'durum':'ATLANDI','aciklama':'Statik denetim gecmedi'})
        outcome={'gorev':jid,'statik_karar':report['decision'],'davranis':behavior,
                 'soz_dizimi_duzeltme':repaired,'ilk_uyarilar':issues,
                 'uzman_raporu':str(report_path),'duzeltilmis_aday':candidate,
                 'karar':'INCELEME_GEREKLI','not':'Guvenilmeyen kod calistirilmadi; insan onayi olmadan yayinlanmaz.'}
        (dest/'SONUC.json').write_text(json.dumps(outcome,ensure_ascii=False,indent=2),encoding='utf-8')
        motor.log('v3_audit_completed',id=jid,static=report['decision'],behavior=behavior['durum'])
        raise motor.QualityRejected('V3 denetim tamamlandi; sonuc SONUC.json dosyasinda, insan onayi gerekli')
    motor.execute=execute
    print('KADO V3: uretim + sinirli duzeltme + statik denetim + guvenli AST davranis testi. Ctrl+C ile durdur.',flush=True)
    try:
        while True:
            if not motor.tick():time.sleep(10)
    except KeyboardInterrupt:print('Motor durduruldu')

if __name__=='__main__':
    if '--selftest' in sys.argv:
        assert behavior_probe('def topla(a,b):\n return a+b\n','iki sayiyi topla')['durum']=='GECTI'
        assert behavior_probe('def topla(a,b):\n return a-b\n','iki sayiyi topla')['durum']=='KALDI'
        assert behavior_probe('import os\ndef topla(a,b):\n return a+b\n','iki sayiyi topla')['durum']=='GECTI'
        assert behavior_probe('def foo(x):\n return x\n','iki sayiyi topla')['durum']=='KAPSAM_DISI'
        print('V3 SELFTEST 4/4 BASARILI (yalnizca AST yorumlayici)')
    else:
        try:main()
        except Exception:traceback.print_exc();sys.exit(1)
