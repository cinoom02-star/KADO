"""KADO queue bridge v2: one model attempt, static audit, review required.
Never executes generated code, modifies production KADO, or publishes content.
"""
import ast
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
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

def main():
    sys.path.insert(0, str(ROOT))
    motor = load('kado_motor', MOTOR_DIR / 'kado_motor.py')
    flow = load('kado_uzman_akis_v1', ROOT / 'kado_uzman_akis_v1.py')
    if not hasattr(motor, 'QualityRejected') or not hasattr(motor, 'code_issues'):
        raise RuntimeError('Kalite V2 motoru bulunamadi; dosyalara dokunulmadi')
    original_execute = motor.execute

    def integrated_execute(job):
        if job['kind'] != 'kod':
            return original_execute(job)
        jid = job['id']
        dest = motor.OUT / jid
        dest.mkdir(parents=True, exist_ok=True)
        motor.log('start', id=jid, kind='kod', mode='single_attempt_audit')
        prompt = ('Sen KADO kod yazari uzmansin. Tek bir calisabilir Python 3 dosyasi yaz. '
                  'Harici kutuphane, os, subprocess, ag, dosya silme, gizli veri kullanma. '
                  'Turkce metinler dogru olsun. Yalnizca ```python kod blogu dondur. Gorev: '
                  + job['goal'])
        raw = motor.ask_model(prompt)
        (dest / 'deneme_1.txt').write_text(raw, encoding='utf-8')
        code = motor.extract_code(raw)
        issues = motor.code_issues(code)
        (dest / 'ON_KONTROL.json').write_text(json.dumps({'issues': issues}, ensure_ascii=False, indent=2), encoding='utf-8')
        motor.log('quality_check', id=jid, attempt=1, issues=issues)
        try:
            ast.parse(code)
        except SyntaxError as exc:
            (dest / 'INCELEME_GEREKLI.txt').write_text('Sozdizimi hatasi: ' + str(exc), encoding='utf-8')
            motor.log('audit_skipped', id=jid, reason='syntax_error')
            raise motor.QualityRejected('Sozdizimi hatasi; uzman AST denetimi calistirilamadi') from exc
        (dest / 'uygulama.py').write_text(code + '\n', encoding='utf-8')
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        try:
            flow.run(dest, REPORT_DIR)
            report_path = REPORT_DIR / (jid + '_uzman_akis.json')
            report = json.loads(report_path.read_text(encoding='utf-8'))
            summary = {'karar': report['decision'], 'ilk_uyarilar': issues,
                       'rapor': str(report_path), 'aday': report['candidate'],
                       'davranis_testi': 'YAPILMADI'}
            (dest / 'UZMAN_DENETIM_SONUCU.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
            motor.log('audit_completed', id=jid, decision=report['decision'])
        except Exception as exc:
            (dest / 'DENETIM_HATASI.txt').write_text(repr(exc), encoding='utf-8')
            motor.log('audit_error', id=jid, error=str(exc)[:250])
            raise motor.QualityRejected('Uzman denetimi tamamlanamadi; manuel inceleme gerekli') from exc
        # No behavior tests and no permission to execute generated programs.
        raise motor.QualityRejected('Uzman statik denetimi kaydedildi; davranis testi ve insan onayi gerekli')

    motor.execute = integrated_execute
    print('KADO V2 basladi: kod icin 1 uretim + uzman denetimi + .review.', flush=True)
    print('Kod calistirilmaz. Ctrl+C ile durdur.', flush=True)
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
