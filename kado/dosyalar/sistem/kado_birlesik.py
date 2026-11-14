"""Launch the existing desktop Kado with attached WhatsApp channels."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import main as desktop
from kado_call.kado_host import install
install(desktop)
desktop.main()
