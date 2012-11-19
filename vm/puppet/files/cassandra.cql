CREATE KEYSPACE handbag11k WITH strategy_class = 'SimpleStrategy'
  AND strategy_options:replication_factor = '1';

USE handbag11k;

CREATE TABLE color_codewords3 (
  KEY blob PRIMARY KEY
) WITH
  comment='' AND
  comparator=blob AND
  read_repair_chance=0.100000 AND
  gc_grace_seconds=864000 AND
  default_validation=blob AND
  min_compaction_threshold=4 AND
  max_compaction_threshold=32 AND
  replicate_on_write='true' AND
  compaction_strategy_class='SizeTieredCompactionStrategy' AND
  compression_parameters:sstable_compression='SnappyCompressor';

CREATE TABLE features (
  KEY blob PRIMARY KEY
) WITH
  comment='' AND
  comparator=blob AND
  read_repair_chance=0.100000 AND
  gc_grace_seconds=864000 AND
  default_validation=blob AND
  min_compaction_threshold=4 AND
  max_compaction_threshold=32 AND
  replicate_on_write='true' AND
  compaction_strategy_class='SizeTieredCompactionStrategy' AND
  compression_parameters:sstable_compression='SnappyCompressor';