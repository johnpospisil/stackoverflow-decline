-- P09 query 2 of 2: monthly QUESTIONS (incl. deleted) for every other non-meta site, in one run.
-- Run at https://data.stackexchange.com/stackoverflow/query/new (any site works; it loops over all databases).
-- Output: one row per database x month. We match database names to our 26 sites afterwards.
DECLARE @sql nvarchar(max) = N'';

SELECT @sql = @sql + N' UNION ALL SELECT ' + QUOTENAME(name, '''') + N' AS db,
    DATEFROMPARTS(YEAR(CreationDate), MONTH(CreationDate), 1) AS month,
    COUNT(*) AS total,
    SUM(CASE WHEN DeletionDate IS NULL THEN 1 ELSE 0 END) AS not_deleted,
    SUM(CASE WHEN DeletionDate IS NOT NULL THEN 1 ELSE 0 END) AS deleted
  FROM ' + QUOTENAME(name) + N'.dbo.PostsWithDeleted
  WHERE PostTypeId = 1 AND CreationDate >= ''2017-01-01'' AND CreationDate < ''2026-10-01''
  GROUP BY DATEFROMPARTS(YEAR(CreationDate), MONTH(CreationDate), 1)'
FROM sys.databases
WHERE state_desc = 'ONLINE'
  AND name <> 'StackOverflow'
  AND name NOT LIKE '%Meta%'
  AND OBJECT_ID(QUOTENAME(name) + '.dbo.PostsWithDeleted') IS NOT NULL;

SET @sql = N'SELECT * FROM (' + STUFF(@sql, 1, LEN(N' UNION ALL '), N'') + N') x ORDER BY db, month';
EXEC sp_executesql @sql;
