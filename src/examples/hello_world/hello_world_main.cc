// Copyright 2012
// Author: Stephen Holiday (stephen.holiday@gmail.com)

#include <gflags/gflags.h>
#include <glog/logging.h>

int main(int argc, char *argv[]) {
  google::ParseCommandLineFlags(&argc, &argv, true);
  google::InitGoogleLogging(argv[0]);
  FLAGS_logtostderr = true;
  
  LOG(INFO) << "Hello world!";
}