---
title: Git merge or rebase?
subtitle: Two ways to bring main into your branch
cols: 2
source: git-scm.com, Pro Git chapter 3.6
---
Both commands put the work from main into your branch. Merge keeps history as it happened. Rebase rewrites your commits so history is one straight line.

## A What each command does {span=2}
```flow LR
(feature branch) -> {Shared with others?}
{Shared with others?} -> git merge main: yes
{Shared with others?} -> git rebase main: no
git merge main -> *[(merge commit)]
git rebase main -> *[(linear history)]
```

## B Pick by situation
| Situation | Merge | Rebase |
|---|---|---|
| Branch others pulled | ok safe | no rewrites their history |
| Local branch, before a PR | warn extra commit | ok clean history |
| Long-running release branch | ok keeps context | no many conflicts |

## C Safe rebase in four steps
1. Run `git fetch origin`.
2. Run `git rebase origin/main`.
3. Fix each conflict and run `git rebase --continue`.
4. Push with `git push --force-with-lease`.

```callout warn Never rebase shared commits
Other people build on those commits. A rebase gives the commits new IDs, and their copies stop matching.
```
