from pathlib import Path
import re

path = Path('apps/server/src/orchestration-v2/runtimeLayer.test.ts')
original = path.read_text()
start = original.index('  it.effect.each([\n    "resume",\n    "resume-started",')
end = original.index('\n  it.', start + 15) if '\n  it.' in original[start + 15:] else len(original)
src = original[start:end]

def once(old: str, new: str) -> None:
    global src
    count = src.count(old)
    if count != 1:
        raise ValueError(f'Expected one occurrence, found {count}: {old[:100]}')
    src = src.replace(old, new)

once('    "wake-after-arm",\n    "stop",', '    "wake-after-arm",\n    "wake-before-arm",\n    "stop-after-arm-wake",\n    "stop-before-arm-wake",\n    "stop",')
block_start = src.index('      if (scenario === "wake-after-arm") {\n        // A notification-only run')
block_end = src.index('\n      let armedShell', block_start)
block = src[block_start:block_end]
assert block.endswith('\n      }')
inner = block[block.index('\n') + 1:-len('\n      }')]
inner = inner.replace('        // A notification-only run after arming must not hide the failed source.\n', '')
inner = re.sub(r'"recovery:armed-notification-wake:([^\"]+)"', r'`recovery:notification-wake:\1:${scenario}`', inner)
helper = '      const writeNotificationWake = Effect.fn("UsageLimitRecoveryTest.writeNotificationWake")(\n        function* () {\n' + '\n'.join('  ' + line for line in inner.split('\n')) + '\n        },\n      );\n'
helper += '''      const hasWake =
        scenario === "wake-after-arm" ||
        scenario === "wake-before-arm" ||
        scenario === "stop-after-arm-wake" ||
        scenario === "stop-before-arm-wake";
      if (scenario === "wake-before-arm" || scenario === "stop-before-arm-wake") {
        yield* writeNotificationWake();
      }
'''
once(block, '''      if (scenario === "wake-after-arm" || scenario === "stop-after-arm-wake") {
        yield* writeNotificationWake();
      }''')
once('      const shell = (yield* orchestrator.getShellSnapshot()).threads.find(', helper + '      const shell = (yield* orchestrator.getShellSnapshot()).threads.find(')
once('        scenario === "stop-before-arm" || scenario === "stop-before-arm-mismatched-recovery";', '''        scenario === "stop-before-arm" ||
        scenario === "stop-before-arm-mismatched-recovery" ||
        scenario === "stop-before-arm-wake";''')
once('      if (scenario === "wake-after-arm") {\n        assert.equal(armedShell.latestRunId, run.id);', '      if (hasWake) {\n        assert.equal(armedShell.latestRunId, run.id);')
once('        scenario === "queued-resume" || scenario === "wake-after-arm" ? 2 : 1,', '        scenario === "queued-resume" || hasWake ? 2 : 1,')
once('      if (scenario === "wake-after-arm") {\n        const store = yield* ProjectionStore.ProjectionStoreV2;', '      if (hasWake) {\n        const store = yield* ProjectionStore.ProjectionStoreV2;')
assert src.count('      if (scenario === "stop") {') == 2
src = src.replace('      if (scenario === "stop") {', '      if (scenario === "stop" || scenario === "stop-after-arm-wake") {')
assert src.count('          scenario === "wake-after-arm" ||\n          stopBeforeArm ||') == 2
src = src.replace('          scenario === "wake-after-arm" ||\n          stopBeforeArm ||', '          scenario === "wake-after-arm" ||\n          scenario === "wake-before-arm" ||\n          stopBeforeArm ||')
once('          commandId: CommandId.make("recovery:rearm-after-stop"),', '          commandId: CommandId.make(`recovery:rearm-after-stop:${scenario}`),')
once('''        yield* orchestrator.dispatch(freshResume!);
        assert.lengthOf((yield* orchestrator.getThreadProjection(threadId)).runs, 2);
      }
      if (scenario === "queued-resume") {''', '''        yield* orchestrator.dispatch(freshResume!);
        assert.lengthOf((yield* orchestrator.getThreadProjection(threadId)).runs, hasWake ? 3 : 2);
      }
      if (scenario === "queued-resume") {''')
path.write_text(original[:start] + src + original[end:])
