// Copyright 2012
// Author: Stephen Holiday (stephen.holiday@gmail.com)

namespace cpp examples.searchengine
namespace py examples.searchengine

struct SearchRequest {
  1: string key,
  2: string url
}

struct SearchResult {
  1: string key,
  2: string url,
  3: double score
}

struct SearchResponse {
  1: list<SearchResult> results,
  2: bool success,
  3: string message
}

service SearchEngineService {
  SearchResponse search(1: SearchRequest request)
  i32 ping()
}