"""KADO existing audit/repair modules orchestrator. No generated-code execution."""
import argparse, datetime, json, pathlib, sys, tempfile
ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from kado_entegre_denetim import check
from kado_guvenli_duzeltme import repair

def run(job_dir, report_dir):
    job=pathlib.Path(job_dir).resolve()
    if not (job/'uygulama.py').is_file(): raise ValueError('uygulama.py bulunamadi')
    report_dir=pathlib.Path(report_dir).resolve(); report_dir.mkdir(parents=True,exist_ok=True)
    initial=check(job)
    source=(job/'uygulama.py').read_text(encoding='utf-8-sig')
    candidate=source; changes=[]; after=initial
    if initial['karar']=='INCELEME_GEREKLI':
        try: candidate,changes=repair(source)
        except SyntaxError: pass
        if changes:
            with tempfile.TemporaryDirectory(prefix='kado_audit_') as temp:
                (pathlib.Path(temp)/'uygulama.py').write_text(candidate,encoding='utf-8')
                after=check(temp)
    approved=after['karar']=='STATIK_KONTROL_GECTI_TEST_GEREKLI'
    # Candidate is only written after a successful audit. Never replace original.
    candidate_path=None
    if changes and approved:
        candidate_path=report_dir/(job.name+'_duzeltilmis_aday.py')
        candidate_path.write_text(candidate,encoding='utf-8')
    decision=('STATIK_KONTROL_GECTI_DAVRANIS_TESTI_GEREKLI' if approved else 'MANUEL_INCELEME_GEREKLI')
    report={'job':str(job),'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'initial':initial,'changes':changes,'after':after,'decision':decision,
            'candidate':str(candidate_path) if candidate_path else None,
            'limitations':['Only known console clear repair is automated','No generated code executed',
                           'U04 model-based repair not connected','U06 checks syntax, not behavior',
                           'Static checks cannot establish security']}
    path=report_dir/(job.name+'_uzman_akis.json')
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'karar':decision,'degisiklik':len(changes),'aday':report['candidate'],'rapor':str(path)},ensure_ascii=False,indent=2))
    return 0 if approved else 2

def main():
    p=argparse.ArgumentParser();p.add_argument('job_dir',nargs='?');p.add_argument('--report-dir');p.add_argument('--selftest',action='store_true');a=p.parse_args()
    if a.selftest:
        with tempfile.TemporaryDirectory(prefix='kado_test_') as d:
            j=pathlib.Path(d)/'sample';j.mkdir()
            (j/'uygulama.py').write_text("import os\ndef main():\n    os.system('cls' if os.name == 'nt' else 'clear')\n    print('OK')\n",encoding='utf-8')
            rc=run(j,pathlib.Path(d)/'reports')
            assert rc==0
            report=json.loads((pathlib.Path(d)/'reports'/'sample_uzman_akis.json').read_text(encoding='utf-8'))
            assert len(report['changes'])==1 and report['candidate']
            assert (j/'uygulama.py').read_text(encoding='utf-8').count('os.system')==1
            print('SELFTEST BASARILI: Risk -> aday duzeltme -> yeniden denetim; orijinal korundu')
        return 0
    if not a.job_dir:p.error('job_dir gerekli')
    return run(a.job_dir,a.report_dir or ROOT/'entegrasyon_raporlari')
if __name__=='__main__':sys.exit(main())
