---
name: tdd
description: Implement a software feature using red-green-refactor test driven development. Use when the user wants you to build a feature with tests
---

tdd helps you build a feature or fix a bug using test-driven development.

The process is simple:

1. Write one test that fails.
2. Write the minimum code needed to make it pass.
3. Move on to the next behaviour.

It also defines some rules for writing useful tests: what should be tested, where tests should sit, when mocks are appropriate, and which testing patterns to avoid.

Before writing any tests, `tdd` identifies the public interfaces it plans to test and asks you to confirm them. This is meant to stop the test suite from covering unnecessary internal details.

`tdd` does not manage the whole implementation process itself. It provides the rules for doing TDD. You or another skill such as `implement` actually drives the work.

## When to use it

Use `/tdd` when you are building a feature or fixing a bug test-first. It may also be selected automatically when you ask for TDD or say "red-green-refactor".

It works best when the behaviour is already clear: there is some input, some expected output or observable result, and you want tests that will still work after the implementation is refactored.

| Situation | Use |
|---|---|
| The behaviour and expected result are clear | `tdd` |
| The behaviour still needs to be defined | `to-spec` |
| You are deciding what the interface should look like | `codebase-design` |
| You already have a spec or tickets and want the whole implementation handled | `implement` |
| The change is simple config, wiring, types, or straightforward CRUD | TDD may not be useful |

There is currently no automatic rule for deciding whether a change is worth testing with TDD at all.

This matters because some changes do not have a meaningful independent result to test. In those cases, you can easily end up writing a test that simply repeats the implementation rather than checking real behaviour.

For now, you have to make that judgement yourself or define the rule in `CLAUDE.md`.

## Requirements

`codebase-design` must be installed.

`tdd` previously contained its own guidance about module and interface design, but that guidance was moved into `codebase-design` in version 1.0.

`tdd` itself does not store state or create any files.

## How the TDD loop works

There are three main rules.

### Red-green

Write one failing test, then write only enough code to make it pass.

Do not write code for behaviours you have not tested yet.

There is no separate refactoring step in this skill. Refactoring is expected to happen later during `code-review`.

### Work in small vertical slices

Implement one small piece of behaviour at a time:

1. Write a test.
2. Make it pass.
3. Repeat.

The first test should ideally prove that one simple path works from beginning to end.

Do not write a large batch of tests first and then implement everything afterwards. Those tests are often based on assumptions about how the code will work rather than on actual behaviour.

### Agree what you are testing first

Tests should normally exercise a public interface rather than internal implementation details.

`tdd` calls this interface a **test seam**.

It will not write a test against a seam that has not already been agreed.

If you use `to-spec` first, those seams are agreed during that process. If you run `tdd` by itself, it asks you to approve them before testing starts.

## Testing mistakes it tries to prevent

### Tests tied to implementation details

A good test should keep passing if the internal code is reorganised but the behaviour stays the same.

Bad signs include:

- mocking your own internal modules
- checking how many times an internal function was called
- testing private functions directly
- querying the database just to check something that could be verified through the public interface

### Tests that repeat the implementation

A test should not calculate its expected result using the same logic as the code being tested.

Expected results should come from an independent source, such as:

- a known value
- a worked example
- the specification

Otherwise the test can be wrong in exactly the same way as the implementation and still pass.

### Writing all the tests first

Do not write a whole batch of tests before implementing anything.

Write one failing test, make it pass, and then write the next one.

## Mocks

Use mocks for things outside your system, such as:

- external APIs
- the current time
- randomness
- sometimes the filesystem
- sometimes the database

Do not normally mock your own modules.