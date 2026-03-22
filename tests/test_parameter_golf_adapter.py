from pathlib import Path
import json
import tempfile
import unittest

from lab.adapters.parameter_golf import ParameterGolfAdapter
from lab.config import Paths
from lab.models import Plan


class ParameterGolfAdapterTests(unittest.TestCase):
    def test_parse_metrics(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        (root / "state").mkdir()
        (root / "logs").mkdir()
        (root / "snapshots" / "research").mkdir(parents=True)
        (root / "config").mkdir()
        (root / "output" / "runs").mkdir(parents=True, exist_ok=True)
        (root / "output" / "public").mkdir(parents=True, exist_ok=True)
        (root / "config" / "runtime.json").write_text(json.dumps({"parameter_golf": {}}))
        adapter = ParameterGolfAdapter(Paths.discover(root))
        text = "step:10/200 val_loss:1.3333 val_bpb:1.2222\nfinal_int8_zlib_roundtrip_exact val_loss:1.11111111 val_bpb:1.00000000\n"
        final = adapter._parse_final_metrics(text)
        rows = adapter._parse_metrics_rows(text)
        self.assertEqual(final["val_bpb"], 1.0)
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
