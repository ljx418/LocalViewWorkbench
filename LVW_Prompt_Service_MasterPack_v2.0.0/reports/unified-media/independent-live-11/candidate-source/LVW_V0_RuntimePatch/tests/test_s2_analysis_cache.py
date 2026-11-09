import math
import unittest

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import NODE_CLASS_MAPPINGS
from LVW_V0_RuntimePatch.tests.test_s2_warm_benchmark import WarmTransport
from LVW_V0_RuntimePatch.tests.test_s2_video_cancel import Frame


class CacheTests(unittest.TestCase):
    def test_registered_image_reanalysis_has_fresh_execution_policy_and_provider_calls(self):
        cls=NODE_CLASS_MAPPINGS['LVWImagePromptBridge']
        self.assertTrue(math.isnan(cls.IS_CHANGED(image_reference='same-image')))
        transport=WarmTransport();node=cls(transport=transport,encoder=lambda frame:'fixture')
        first=node.analyze([Frame()]);second=node.analyze([Frame()])
        self.assertEqual(2,transport.calls);self.assertEqual(2,transport.cleanups)
        self.assertEqual(first['result'][1],second['result'][1])
        self.assertEqual(transport.payloads[0],transport.payloads[1])
        self.assertFalse(hasattr(NODE_CLASS_MAPPINGS['LVWManualPromptOwner'],'IS_CHANGED'))


if __name__=='__main__':unittest.main()
