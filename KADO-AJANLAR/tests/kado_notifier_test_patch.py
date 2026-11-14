    async def _agent_meeting_notifier(self):
        """Yeni tamamlanan toplantilari ayri ayri takip eder."""
        import sqlite3
        import json
        from pathlib import Path

        root = Path(r"C:\KADO\KADO-AJANLAR")
        db = root / "memory" / "kado_company.db"
        test_db = root / "memory" / "kado_notifier_test.db"
        if test_db.exists():
            db = test_db
        state = root / "memory" / "kado_notifier_v3.json"
        old_state = root / "memory" / "kado_notifier_seen.txt"

        def read_meetings():
            con = sqlite3.connect(
                f"file:{db.as_posix()}?mode=ro",
                uri=True,
                timeout=3
            )
            try:
                return con.execute(
                    "SELECT id, status FROM meetings ORDER BY id"
                ).fetchall()
            finally:
                con.close()

        def save_state(data):
            temp = state.with_suffix(".tmp")
            temp.write_text(
                json.dumps(data, ensure_ascii=False),
                encoding="utf-8"
            )
            temp.replace(state)

        if state.exists():
            data = json.loads(state.read_text(encoding="utf-8"))
        else:
            rows = await asyncio.to_thread(read_meetings)
            baseline = max((mid for mid, _ in rows), default=0)

            if old_state.exists():
                baseline = max(
                    baseline,
                    int(old_state.read_text(encoding="utf-8").strip())
                )

            data = {
                "baseline": baseline,
                "notified": []
            }
            save_state(data)

        while True:
            try:
                rows = await asyncio.to_thread(read_meetings)
                baseline = int(data["baseline"])
                notified = set(data["notified"])

                for mid, status in rows:
                    if mid <= baseline or status != "completed":
                        continue
                    if mid in notified:
                        continue

                    # Tekrar bildirim riskini azaltmak icin
                    # ses kuyru?una eklemeden once kaydet.
                    notified.add(mid)
                    data["notified"] = sorted(notified)
                    save_state(data)

                    message = (
                        "Reis, ekip toplantiyi bitirdi. "
                        "Dort ajanin raporu hazir. "
                        "Istersen sonuclari anlatayim."
                    )

                    try:
                        self.ui.write_log(
                            f"KADO: Toplanti #{mid} tamamlandi."
                        )
                    except Exception:
                        pass

                    if self._el_on and self._el_queue is not None:
                        await self._el_queue.put(message)
                    else:
                        from actions.tts import speak_text
                        await asyncio.to_thread(speak_text, message)

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"[KADO] Ajan bildirimi: {exc}")

            await asyncio.sleep(5)
