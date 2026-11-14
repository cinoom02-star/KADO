"""Read-only bridge: existing KADO U05/U06/U07/U18/U19 inspect V2 job outputs."""
import argparse, ast, json, pathlib, sys, datetime
ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from kado_19_uzman import kadro_kontrol
from kado_guvenlik_kalite import GuvenlikDenetcisi

def check(job_dir):
    job_dir=pathlib.Path(job_dir).resolve()
    if not job_dir.is_dir(): raise ValueError('Gorev klasoru bulunamadi')
    kadro_kontrol()
    result={'gorev':job_dir.name,'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'uzmanlar':{},'karar':'INCELEME_GEREKLI'}
    py=job_dir/'uygulama.py'
    social=job_dir/'paylasim_taslagi.txt'
    if py.is_file():
        source=py.read_text(encoding='utf-8-sig')
        try:
            tree=ast.parse(source)
            result['uzmanlar']['U05']={'durum':'GECTI','aciklama':'AST sozdizimi gecerli'}
        except SyntaxError as e:
            result['uzmanlar']['U05']={'durum':'RED','hata':str(e)}
            tree=None
        if tree:
            try:
                from kado_kod_ekibi_v2 import u06_dogrula
                ok,msg=u06_dogrula(source)
            except ImportError as e:
                ok=False
                msg="U06 bagimliligi eksik: "+str(e)
            result['uzmanlar']['U06']={'durum':'GECTI' if ok else 'RED','aciklama':str(msg)}
            d=GuvenlikDenetcisi();d.visit(tree)
            result['uzmanlar']['U07']={'durum':'INCELEME' if d.bulgular else 'ON_KONTROL_GECTI','bulgular':d.bulgular}
            result['uzmanlar']['U18']={'durum':'SINIRLI_STATIK_KONTROL','satir':len(source.splitlines()),'fonksiyon':sum(isinstance(x,ast.FunctionDef) for x in ast.walk(tree))}
            result['karar']='STATIK_KONTROL_GECTI_TEST_GEREKLI' if ok and not d.bulgular else 'INCELEME_GEREKLI'
    elif social.is_file():
        content=social.read_text(encoding='utf-8-sig')
        issues=[]
        import re
        if re.search(r'(?i)ic camaşırı|iç çamaşırı|seviş|porno|sikiş',content):issues.append('Marka icin uygunsuz ifade')
        if re.search(r'[ÃÄÅ�]|\ufffd',content):issues.append('Kodlama bozuklugu olasiligi')
        if len(content)<100:issues.append('Cok kisa metin')
        result['uzmanlar']['U18']={'durum':'RED' if issues else 'SINIRLI_ON_KONTROL','bulgular':issues}
        result['karar']='RED' if issues else 'INSAN_ONAYI_GEREKLI'
    else: result['hata']='Desteklenen cikti yok'
    result['uzmanlar']['U19']={'durum':'RAPOR_HAZIR'}
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('job_dir');p.add_argument('--report-dir');a=p.parse_args()
    result=check(a.job_dir)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if a.report_dir:
        out=pathlib.Path(a.report_dir);out.mkdir(parents=True,exist_ok=True)
        target=out/(result['gorev']+'_denetim.json')
        target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print('RAPOR:',target)
    return 0 if result['karar'] not in ('RED','INCELEME_GEREKLI') else 1
if __name__=='__main__':sys.exit(main())
