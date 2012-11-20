// Copyright 2012
// Author: Stephen Holiday (stephen.holiday@gmail.com)

#ifndef EXAMPLES_SEARCH_ENGINE_SEARCH_ENGINE_IMPL_H_
#define EXAMPLES_SEARCH_ENGINE_SEARCH_ENGINE_IMPL_H_

#include "examples/search_engine/thrift/gen-cpp/SearchEngineService.h"

namespace examples {
namespace searchengine {

class SearchEngineServiceImpl : virtual public SearchEngineServiceIf {
 public:
  SearchEngineServiceImpl() {};
  void search(SearchResponse& response, const SearchRequest& request);
  int32_t ping();
};
}  // namespace searchengine
}  // namespace examples

#endif  // EXAMPLES_SEARCH_ENGINE_SEARCH_ENGINE_IMPL_H_