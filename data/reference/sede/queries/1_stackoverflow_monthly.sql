-- P09 query 1 of 2: Stack Overflow monthly questions and answers, including deleted posts.
-- Run at https://data.stackexchange.com/stackoverflow/query/new
-- If it times out, change the two dates below (e.g. 2017-01-01..2020-01-01, then 2020..2023, then 2023..2026-10-01)
-- and run it once per chunk; save each result as its own CSV.
DECLARE @start date = '##StartDate:string?2017-01-01##';
DECLARE @end   date = '##EndDate:string?2026-10-01##';
DECLARE @snapshot datetime = (SELECT MAX(CreationDate) FROM Posts);

SELECT
  DATEFROMPARTS(YEAR(CreationDate), MONTH(CreationDate), 1) AS month,
  PostTypeId,
  COUNT(*) AS total,
  SUM(CASE WHEN DeletionDate IS NULL THEN 1 ELSE 0 END) AS not_deleted,
  SUM(CASE WHEN DeletionDate IS NOT NULL THEN 1 ELSE 0 END) AS deleted,
  @snapshot AS sede_snapshot
FROM PostsWithDeleted
WHERE PostTypeId IN (1, 2)
  AND CreationDate >= @start AND CreationDate < @end
GROUP BY DATEFROMPARTS(YEAR(CreationDate), MONTH(CreationDate), 1), PostTypeId
ORDER BY month, PostTypeId;
