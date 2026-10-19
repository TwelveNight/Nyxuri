"""Private updater checks must not deploy or lose the AI conflict instructions."""
import contextlib
import io
import json
import subprocess
import unittest
from unittest.mock import Mock, patch
from tests.utils import TempEnv
from personal import update

class UpdateCheckTests(unittest.TestCase):
    def test_managed_check_delegates_without_installing(self):
        with TempEnv() as ctx:
            registry = ctx.home / '.config/desktop-profiles/profiles.json'
            registry.parent.mkdir()
            registry.write_text('{}')
            helper = ctx.home / '.local/bin/desktop-update'
            helper.write_text('#!/bin/sh\n')
            with patch.object(update.subprocess, 'run', return_value=Mock(returncode=0)) as run:
                self.assertEqual(update.main(['--check']), 0)
            run.assert_called_once_with([str(helper), 'check', 'nyxuri'], check=False)

    def test_fallback_check_fetches_and_reports_without_merge_or_deploy(self):
        with TempEnv(), patch.object(update, 'git', side_effect=[
                'night/personal-overlay', 'https://github.com/ech678/Nyxuri.git', '', '2 3']) as git, \
                patch.object(update, 'deploy') as deploy:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(update.main(['--check']), 0)
            self.assertEqual(json.loads(output.getvalue())['behind'], 3)
            self.assertEqual(git.call_args_list[-2].args,
                             ('-c', 'http.lowSpeedTime=15', '-c', 'http.lowSpeedLimit=1000', 'fetch', 'origin', 'main'))
            self.assertEqual(git.call_args_list[-1].args, ('rev-list', '--left-right', '--count', 'HEAD...FETCH_HEAD'))
            self.assertFalse(any(call.args[0] == 'merge' for call in git.call_args_list))
            deploy.assert_not_called()

    def test_fallback_conflict_keeps_merge_and_prints_ai_instructions(self):
        calls = []
        def git(*args):
            calls.append(args)
            if args == ('branch', '--show-current'): return 'night/personal-overlay'
            if args == ('remote', 'get-url', 'origin'): return 'https://github.com/ech678/Nyxuri.git'
            if args[0] == 'merge': raise subprocess.CalledProcessError(1, ['git', *args])
            if args[0] == 'diff': return 'units/niri/config.kdl'
            return ''
        with TempEnv(), patch.object(update, 'git', side_effect=git), \
                patch.object(update.shutil, 'which', return_value=None), patch.object(update, 'deploy') as deploy:
            output = io.StringIO()
            with contextlib.redirect_stderr(output):
                self.assertEqual(update.main([]), 1)
            self.assertIn('打开 AI', output.getvalue())
            self.assertIn('live 未更新', output.getvalue())
            self.assertIn(('merge', '--no-edit', 'FETCH_HEAD'), calls)
            self.assertFalse(any(call[0] in ('reset', 'stash', 'rebase', 'push', 'add', 'commit') for call in calls))
            deploy.assert_not_called()
