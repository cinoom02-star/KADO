"""Run existing KADO V2 queue with mandatory static audit for code jobs.
Does not alter existing modules or execute generated programs.
"""
import importlib.util
import json
import pathlib
import sys
import time
import traceback

ROOT = pathlib.Path(__file__).resolve().parent
MOTOR_DIR = ROOT / 'kado_agent_motor'
REPORT_DIR = ROOT / 'entegrasyon_raporlari'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Modul bulunamadi: {path}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    if not (MOTOR_DIR / 'kado_motor.py').is_file():
        raise RuntimeError('Motor bulunamadi')
    sys.path.insert(0, str(ROOT))
    motor = load('kado_motor', MOTOR_DIR / 'kado_motor.py')
    flow = load('kado_uzman_akis_v1', ROOT / 'kado_uzman_akis_v1.py')
    if not hasattr(motor, 'QualityRejected'):
        raise RuntimeError('Kalite V2 motoru gerekli')
    original_execute = motor.execute

    def audited_execute(job):
        original_execute(job)
        if job['kind'] != 'kod':
            return
        jid = job['id']
        report_dir = REPORT_DIR
        report_dir.mkdir(parents=True, exist_ok=True)
        result = flow.run(MOTOR_DIR / 'ciktilar' / jid, report_dir)
        report_path = report_dir / (jid + '_uzman_akis.json')
        report = json.loads(report_path.read_text(encoding='utf-8'))
        dest = MOTOR_DIR / 'ciktilar' / jid
        (dest / 'UZMAN_DENETIM_SONUCU.json').write_text(
            json.dumps({'karar': report['decision'], 'rapor': str(report_path),
                        'aday': report['candidate']}, ensure_ascii=False, indent=2),
            encoding='utf-8')
        if result != 0:
            raise motor.QualityRejected('Uzman denetimi gecmedi: ' + report['decision'])
        # Static audit is NOT a behavioral test: require human review, not .done.
        raise motor.QualityRejected('Statik kontrol gecti; davranis testi ve insan onayi gerekli')

    motor.execute = audited_execute
    print('KADO birlesik motor basladi. Kod gorevleri statik kontrolden sonra .review olur.', flush=True)
    print('Uretilen kod calistirilmaz. Durdurmak icin Ctrl+C.', flush=True)
    try:
        while True:
            if not motor.tick():
                time.sleep(10)
    except KeyboardInterrupt:
        print('Motor durduruldu')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
