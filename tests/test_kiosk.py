"""Exercise the launcher with fake display/browser commands, without hardware."""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(shutil.which('bash'), 'Bash is required for the X11 launcher')
class KioskLauncher(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'scripts').mkdir();(self.root/'bin').mkdir()
        shutil.copyfile(ROOT/'scripts/kiosk.sh',self.root/'scripts/kiosk.sh')
        (self.root/'scripts/display-power.py').write_text('import time\ntime.sleep(60)\n')
        self.log=self.root/'calls.log'
        for name in ['xrandr','xinput','xset','chromium']:
            path=self.root/'bin'/name
            path.write_text('#!/bin/sh\nprintf "%s %s\\n" "${0##*/}" "$*" >> "$TEST_LOG"\nif [ "${0##*/}" = chromium ]; then exec sleep 60; fi\n')
            path.chmod(0o755)
        self.env={**os.environ,'PATH':str(self.root/'bin')+os.pathsep+os.environ['PATH'],'TEST_LOG':str(self.log),'XDG_SESSION_TYPE':'x11','XDG_CACHE_HOME':str(self.root/'cache')}
        self.env.pop('MONITOR_COUNT',None)
        self.process=None
    def tearDown(self):
        if self.process and self.process.poll() is None:
            os.killpg(self.process.pid,signal.SIGTERM)
            self.process.communicate(timeout=5)
        self.temp.cleanup()
    def config(self,extra=''):
        (self.root/'kiosk.env').write_text('CALENDAR_URL=http://calendar.test\nLEFT_OUTPUT=HDMI-1\nLEFT_TOUCH="First Touch"\n'+extra)
    def start(self):
        self.process=subprocess.Popen(['bash',str(self.root/'scripts/kiosk.sh')],env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    def await_browsers(self,count):
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if self.log.exists():
                lines=self.log.read_text().splitlines()
                if len([s for s in lines if s.startswith('chromium ')])>=count:return lines
            if self.process.poll() is not None:
                self.fail('Launcher exited: '+self.process.communicate()[1])
            time.sleep(.03)
        self.fail('Browser did not launch')
    def test_default_single_needs_no_second_output_or_touch(self):
        self.config();self.start();lines=self.await_browsers(1)
        self.assertEqual(len([s for s in lines if s.startswith('chromium ')]),1)
        self.assertTrue(any('screen=left&touch=1' in s for s in lines))
        self.assertFalse(any('screen=right' in s or 'HDMI-2' in s for s in lines))
        self.assertIn('xinput map-to-output First Touch HDMI-1',lines)
    def test_two_screens_launch_and_map_independently(self):
        self.config('MONITOR_COUNT=2\nRIGHT_OUTPUT=HDMI-2\nRIGHT_TOUCH="Second Touch"\nSCREEN_WIDTH=1920\nSCREEN_HEIGHT=1080\n')
        self.start();lines=self.await_browsers(2)
        self.assertTrue(any('screen=left&touch=1' in s for s in lines))
        self.assertTrue(any('screen=right&touch=1' in s and '--window-position=1920,0' in s for s in lines))
        self.assertIn('xinput map-to-output Second Touch HDMI-2',lines)
    def test_dual_mode_requires_second_hardware_configuration(self):
        self.config('MONITOR_COUNT=2\n');self.start()
        _,error=self.process.communicate(timeout=5)
        self.assertNotEqual(self.process.returncode,0)
        self.assertIn('RIGHT_OUTPUT',error)
        self.assertFalse(self.log.exists())
    def test_invalid_monitor_count_rejected_before_hardware_calls(self):
        self.config('MONITOR_COUNT=3\n');self.start()
        _,error=self.process.communicate(timeout=5)
        self.assertNotEqual(self.process.returncode,0)
        self.assertIn('MONITOR_COUNT must be 1 or 2',error)
        self.assertFalse(self.log.exists())

if __name__=='__main__':unittest.main()
