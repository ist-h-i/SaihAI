import os
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from app.integrations import bedrock  # noqa: E402


class FakeConfig:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs


class FakeClient:
    def __init__(self, service_name: str, region_name: str | None, config: FakeConfig | None) -> None:
        self.service_name = service_name
        self.region_name = region_name
        self.config = config


class BedrockClientCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        bedrock._clear_bedrock_client_cache()
        self._install_fakes()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        bedrock._clear_bedrock_client_cache()

    def _install_fakes(self) -> None:
        fake_boto3 = types.SimpleNamespace()

        def client(service_name, region_name=None, config=None):
            return FakeClient(service_name, region_name, config)

        fake_boto3.client = client
        sys.modules["boto3"] = fake_boto3

        fake_botocore_config = types.ModuleType("botocore.config")
        fake_botocore_config.Config = FakeConfig
        sys.modules["botocore.config"] = fake_botocore_config

        fake_botocore = types.ModuleType("botocore")
        fake_botocore.config = fake_botocore_config
        sys.modules["botocore"] = fake_botocore

    def test_client_cached_with_config(self) -> None:
        os.environ["BEDROCK_CONNECT_TIMEOUT_MS"] = "500"
        os.environ["BEDROCK_READ_TIMEOUT_MS"] = "1500"
        os.environ["BEDROCK_MAX_ATTEMPTS"] = "2"
        os.environ["BEDROCK_RETRY_MODE"] = "standard"

        client1, reused1, settings1 = bedrock._build_bedrock_client("us-east-1")
        client2, reused2, settings2 = bedrock._build_bedrock_client("us-east-1")

        self.assertIs(client1, client2)
        self.assertFalse(reused1)
        self.assertTrue(reused2)
        self.assertEqual(settings1, (500, 1500, 2, "standard"))
        self.assertEqual(settings1, settings2)
        self.assertEqual(client1.service_name, "bedrock-runtime")
        self.assertEqual(client1.region_name, "us-east-1")
        self.assertIsNotNone(client1.config)
        self.assertEqual(client1.config.kwargs["connect_timeout"], 0.5)
        self.assertEqual(client1.config.kwargs["read_timeout"], 1.5)
        self.assertEqual(client1.config.kwargs["retries"]["max_attempts"], 2)
        self.assertEqual(client1.config.kwargs["retries"]["mode"], "standard")


if __name__ == "__main__":
    unittest.main()
