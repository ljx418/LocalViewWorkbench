# Fixed component cases

The16 rows below are component obligations, not a replacement for product29. All are NOT_RUN. Tests must drive real public handlers/repository/state transitions, with the declared failure/cleanup oracle. Exact nodes and schema are in04-acceptance-matrix.json.

|ID|Oracle|
|---|---|
|PP01|Unknown/nonempty-unversioned or malformed schema is refused without data/schema mutation; no recreation.|
|PP02|Fresh atomic version1 core+private bootstrap, reopen, no scene/FTS/V2 tables; bootstrap fault rollback.|
|PP03|Public create manual empty/media-less shot, get then newapp same root reads identical draft/ETag with provider calls0.|
|PP04|Synthetic image through publicupload/get survives restart, rawsource hash and storedcopy hash distinct and correct; uploadfields canonical/nullsource.|
|PP05|Samekey/samepayload acrossrestart returns original shot/media; changedpayload409 and no duplicate/deletion.|
|PP06|MissingIfMatch428, old412, validPUT updatesdraft/tag nothead/history; restart retainscommit.|
|PP07|Two actual repo connections/public requests race sameETag; exactlyone commits and loser412, no lostupdate.|
|PP08|Publicmanualrevision saves parent/head/draft/idempotency atomically; replay no newhead; model_adopted422 no write.|
|PP09|Public-created revision cannot UPDATE/DELETE through actualSQL; later humanedits preserve old bytes/hash.|
|PP10|Publicpagination exact1/100 and one-over0/101, cursorcrossshot/malformed negative; restartstable no omissions/duplicates.|
|PP11|RealSQL fault between insertrevision andhead update rolls back revision/head/key; olddraft/history preserved; no fake200.|
|PP12|CanonicalChinese/English/locks/controlquotes/SQLlookingtext preserved, parameterizedSQL, invalid/extra/nonfinitepayload422 no sideeffects.|
|PP13|ActualDBfail publicupload removes onlynewuncommittedcopy, retains alloldfiles/rows/key; retrynot automatic.|
|PP14|Missing/substitutedcopy ormaliciousstoredname/symlink failsclosed without escape/delete/sourcehashrewrite.|
|PP15|ActualheldDBlock/readonly failure produces boundedstable503, rollback/no corruption, allownedconnections closed.|
|PP16|Existingmedia/health/envelopes and analysis/runtime DTOs unchanged, manualpath never invokes provider/runtime; no overlay routes activated.|
