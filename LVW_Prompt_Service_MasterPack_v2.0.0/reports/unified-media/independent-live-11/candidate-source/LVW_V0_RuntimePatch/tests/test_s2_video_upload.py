import asyncio
from hashlib import sha256
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_upload import receive_video


async def chunks(*parts):
    for part in parts:yield part


class UploadTests(unittest.TestCase):
    def test_complete_bounded_stream_returns_opaque_reference_and_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            result=asyncio.run(receive_video(temp,'.mp4',chunks(b'ab',b'cd'),max_bytes=4))
            self.assertEqual(4,result['bytes']);self.assertEqual(sha256(b'abcd').hexdigest(),result['sha256'])
            self.assertEqual(b'abcd',(Path(temp)/result['video_reference']).read_bytes())
            self.assertEqual([result['video_reference']],[p.name for p in Path(temp).iterdir()])
            self.assertNotIn(temp,str(result))

    def test_one_over_empty_extension_and_interruption_leave_no_file(self):
        async def interrupted():
            yield b'ab'
            raise asyncio.CancelledError()
        with tempfile.TemporaryDirectory() as temp:
            for extension,stream,error in [('.mp4',chunks(b'abcd',b'e'),BridgeError),
                    ('.mov',chunks(),BridgeError),('../bad.mp4',chunks(b'a'),BridgeError),
                    ('.mp4',interrupted(),asyncio.CancelledError)]:
                with self.subTest(extension=extension),self.assertRaises(error):
                    asyncio.run(receive_video(temp,extension,stream,max_bytes=4))
                self.assertEqual([],list(Path(temp).iterdir()))

    def test_destination_collision_never_overwrites_or_deletes_existing_file(self):
        with tempfile.TemporaryDirectory() as temp:
            existing=Path(temp)/'lvw-upload-fixed.mp4';existing.write_bytes(b'existing')
            with patch('uuid.uuid4',return_value=SimpleNamespace(hex='fixed')):
                with self.assertRaises(BridgeError):asyncio.run(receive_video(temp,'.mp4',chunks(b'new')))
            self.assertEqual(b'existing',existing.read_bytes())
            self.assertEqual([existing],list(Path(temp).iterdir()))

    def test_redirected_root_is_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as temp:
            actual=Path(temp)/'actual';actual.mkdir();link=Path(temp)/'link';link.symlink_to(actual,target_is_directory=True)
            with self.assertRaises(BridgeError):asyncio.run(receive_video(link,'.mp4',chunks(b'no')))
            self.assertEqual([],list(actual.iterdir()))

    def test_missing_input_root_returns_sanitized_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(BridgeError) as caught:
                asyncio.run(receive_video(Path(temp)/'missing','.mp4',chunks(b'no')))
            self.assertEqual('MEDIA_INVALID',caught.exception.code)
            self.assertNotIn(temp,caught.exception.message)
            self.assertEqual([],list(Path(temp).iterdir()))


if __name__=='__main__':unittest.main()
