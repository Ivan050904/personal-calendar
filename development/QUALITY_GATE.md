# Quality Gate

After every wave:
1. implement;
2. targeted tests;
3. regression tests;
4. frontend typecheck if touched;
5. backend typecheck if touched;
6. lint;
7. build;
8. fix failures;
9. rerun;
10. update CURRENT_TASK.md;
11. update CHANGELOG.md;
12. continue automatically.

Never delete/disable tests to make green.

Stop only for a real requirement conflict, destructive unsafe migration, unavailable essential dependency, missing business rule that cannot be safely inferred, or unresolved critical failing test.

Do not stop just because a wave ended.
