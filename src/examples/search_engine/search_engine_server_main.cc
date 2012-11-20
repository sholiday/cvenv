// Copyright 2012
// Author: Stephen Holiday (stephen.holiday@gmail.com)

#include <gflags/gflags.h>
#include <glog/logging.h>
#include <thrift/concurrency/PosixThreadFactory.h>
#include <thrift/concurrency/ThreadManager.h>
#include <thrift/protocol/TBinaryProtocol.h>
#include <thrift/server/TSimpleServer.h>
#include <thrift/server/TThreadedServer.h>
#include <thrift/server/TThreadPoolServer.h>
#include <thrift/transport/TServerSocket.h>
#include <thrift/transport/TTransportUtils.h>

#include "examples/search_engine/search_engine_impl.h"
#include "examples/search_engine/thrift/gen-cpp/SearchEngineService.h"

using apache::thrift::protocol::TBinaryProtocolFactory;
using apache::thrift::server::TSimpleServer;
using apache::thrift::transport::TFramedTransportFactory;
using apache::thrift::transport::TProcessor;
using apache::thrift::transport::TProtocolFactory;
using apache::thrift::transport::TServerSocket;
using apache::thrift::transport::TServerTransport;
using apache::thrift::transport::TTransportFactory;
using boost::shared_ptr;
using examples::searchengine::SearchEngineServiceImpl;
using examples::searchengine::SearchEngineServiceProcessor;

DEFINE_int32(port, 9001, "Port to bind the service to.");

int main(int argc, char **argv) {
  google::InitGoogleLogging(argv[0]);
  google::ParseCommandLineFlags(&argc, &argv, false);
  
  shared_ptr<SearchEngineServiceImpl> handler(new SearchEngineServiceImpl());
  shared_ptr<TProcessor> processor(new SearchEngineServiceProcessor(handler));
  shared_ptr<TServerTransport> serverTransport(new TServerSocket(FLAGS_port));
  shared_ptr<TTransportFactory> transportFactory(
      new TFramedTransportFactory());
  shared_ptr<TProtocolFactory> protocolFactory(new TBinaryProtocolFactory());

  TSimpleServer server(processor, serverTransport,
                       transportFactory, protocolFactory);

  LOG(INFO) << "Starting to listen on port " << FLAGS_port;
  server.serve();
  return 0;
}

