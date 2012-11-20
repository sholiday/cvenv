#!/usr/bin/env python

import sys
sys.path.append('src/examples/search_engine/thrift/gen-py')

from examples.searchengine import SearchEngineService
from examples.searchengine.ttypes import *

from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol

def main():
  # Create a socket to the server.
  transport = TSocket.TSocket('localhost', 9001)
  # Use a framing transport.
  transport = TTransport.TFramedTransport(transport)
  # Use a binary protocol.
  protocol = TBinaryProtocol.TBinaryProtocol(transport)
  # Create the client wrapper.
  client = SearchEngineService.Client(protocol)
  # Connect to the server.
  transport.open()
  
  # Attempt to ping the server.
  print "Ping result: %s" % client.ping()
  
  # Create a fake search request.
  request = SearchRequest(url="http://example.com/img.png")
  
  # Send the request.
  print "Sending request..."
  response = client.search(request)
  print "Recieved response."
  
  if response.success:
    print "Search was a success!"
  else:
    print "Search was a failure."

  print "The results are:"
  for result in response.results:
      print '(Key: %s, Score: %s)' % (result.key, result.score)
  
  transport.close()

if __name__ == '__main__':
  main()
