import importlib.util
from unittest.mock import patch
from io import StringIO

spec = importlib.util.spec_from_file_location(
    "oyun", "uygulama_duzeltilmis.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def test(inputs, expected, attempts):
    output = StringIO()
    with patch.object(mod.random, "randint", return_value=50):
        with patch("builtins.input", side_effect=inputs):
            with patch("sys.stdout", output):
                mod.run_game()

    result = output.getvalue()
    assert expected in result, result
    assert f"{attempts} denemede" in result, result

test(["50"], "Tebrikler", 1)
test(["20", "80", "50"], "Tebrikler", 3)
test(["abc", "50"], "gecerli bir tam sayi", 1)
test(["0", "101", "50"], "1 ile 100 arasinda olmali", 1)

print("4/4 DAVRANIS TESTI BASARILI")
