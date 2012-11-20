// Copyright 2012
// Author: Stephen Holiday (stephen.holiday@gmail.com)

#include <boost/lexical_cast.hpp>
#include <glog/logging.h>

#include "examples/search_engine/search_engine_impl.h"
#include "examples/search_engine/thrift/gen-cpp/SearchEngineService.h"

using boost::lexical_cast;

namespace examples {
namespace searchengine {
void SearchEngineServiceImpl::search(SearchResponse& response, const SearchRequest& request) {
  LOG(INFO) << "Recieved a search request.";
  
  // Add some fake results.
  for (int i = 0; i < 3; ++i) {
    SearchResult result;
    result.__set_key("result_" + lexical_cast<std::string>(i));
    result.__set_score(0.5 / (i + 1));
    response.results.push_back(result);
  }
  response.__isset.results = true;
  
  response.__set_success(true);
  LOG(INFO) << "Returning " << response.results.size() << " results.";
}
int32_t SearchEngineServiceImpl::ping() {
  LOG(INFO) << "Recieved a ping.";
  return 42;
}
}  // namespace searchengine
}  // namespace examples