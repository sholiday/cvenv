# Setting up a  C++ Development Environment for Computer Vision

This document describes how to setup a C++ development environment for computer
vision work.

## Overview of Technologies

* Virtual Machine
 * [Virtual Box](https://www.virtualbox.org/) - Similar in purpose to VMWare or
   Xen.
 * [Vagrant](http://vagrantup.com/) - An easy way to configure manage virtual
   machines in a reproducible manner. 
* C++ Libraries
 * [Boost](http://www.boost.org/) - Portable reasonable quality libraries.
 * [OpenCV](http://opencv.org/)
 * [Thrift](http://thrift.apache.org/) - Facebook's cross-language RPC
   framework.
* [SEBS/Blaze](http://code.google.com/p/sebs/) - Build system similar in
  appearance to Google's Blaze.

## Prerequisites
You need to install [Virtual Box](https://www.virtualbox.org/wiki/Downloads).
If you are using OS X or Windows there are packages for you. There is also
probably a package for your Linux distribution.

You also need to install Vagrant, there are several packages
[here](http://downloads.vagrantup.com/).

## Downloading the VM
The time to compile and configure (even though it is scripted) the environment
is not insignificant. So I have provided an image with everything installed.

Navigate to the `vm` directory and run:

    wget https://s3.amazonaws.com/data/vm/precise64-v1.box
    vagrant box add precise64-v1 precise64-v1.box
    rm precise64-v1.box

Now let's boot up the virtual machine:

    vagrant up
    [default] Importing base box 'precise64-v1'...
    [default] The guest additions on this VM do not match the install version of
    VirtualBox! This may cause things such as forwarded ports, shared
    folders, and more to not work properly. If any of those things fail on
    this machine, please update the guest additions and repackage the
    box.

    Guest Additions Version: 4.2.0
    VirtualBox Version: 4.2.4
    [default] Matching MAC address for NAT networking...
    [default] Clearing any previously set forwarded ports...
    [default] Forwarding ports...
    [default] -- 22 => 2222 (adapter 1)
    [default] Creating shared folders metadata...
    [default] Clearing any previously set network interfaces...
    [default] Running any VM customizations...
    [default] Booting VM...
    [default] Waiting for VM to boot. This can take a few minutes.
    [default] VM booted and ready for use!
    [default] Mounting shared folders...
    [default] -- v-root: /vagrant
    [default] -- v-depot: /cvenv/depot
    [default] -- v-puppet-files: /etc/puppet/files
    [default] -- manifests: /tmp/vagrant-puppet/manifests
    [default] Running provisioner: Vagrant::Provisioners::Puppet...
    [default] Running Puppet with /tmp/vagrant-puppet/manifests/precise64.pp...
    stdin: is not a tty
    notice: Scope(Class[main]): Running configure scripts,
    this make take a long time for the first boot...
    notice: Scope(Class[Users]): Users

    info: Applying configuration version '1353361028'
    notice: /Stage[main]//Exec[apt-update]/returns: executed successfully
    notice: Finished catalog run in 35.62 seconds
    
If you get an error:

    vagrant ssh
    
    The private key to connect to this box via SSH has invalid permissions
    set on it. The permissions of the private key should be set to 0600, otherwise SSH will
    ignore the key. Vagrant tried to do this automatically for you but failed. Please set the
    permissions on the following file to 0600 and then try running this command again:

    /Users/stephen/Documents/Projects/cvenv/vm/puppet/files/id_rsa
    $ chmod 666 /Users/stephen/Documents/Projects/cvenv/vm/puppet/files/id_rsa

## Building Code
SSH into the Virtual Machine:

    vagrant ssh
    
Then

    cd /cvenv/depot
    
And compile

    $ blaze build src/examples/hello_world:all
    examples/hello_world:hello_world_main
    configure: C++ compiler flags -O3 -std=c++0x -Wno-deprecated -I/usr/local/include/ -I/usr/local/include/thrift/ -L/usr/lib -L/usr/local/lib 
    configure: C++ compiler g++
    *compile: src/examples/hello_world/hello_world_main.cc
    compile: src/examples/hello_world/hello_world_main.cc
    link: examples/hello_world:hello_world_main
    
    $ ./bin/examples/hello_world/hello_world_main
    I1119 20:16:53.429513  1347 hello_world_main.cc:12] Hello world!

## Vagrant Commands

* `vagrant up` - Start the VM
* `vagrant halt` - Shutdown the VM
 * You can also use `sudo shutdown -h now` from inside the VM.
* `vagrant ssh` - SSH into the VM.
* `vagrant status` - Current status of VMs.

## RPC Overview
For some computer vision projects, you may want to have a web interface to your
C++ code. A common pattern is to have a simple frontend server running a
scripting language like Python/PHP/Ruby connect to a backend C++ server.

The servers may be on the same machine or different machines. This pattern
creates a nice separation of presentation logic and backend computation.

A common library used for the communication between the backend and frontend
pieces is [Thrift](http://thrift.apache.org/). Thrift is an Remote Procedure
Call (RPC) framework. We can write a server in C++ that performs heavy
calculations which we can call from our simple Python application.

### Thrift Example
Let's say we have some C++ code which returns search results for a given query.
We can define an interface like so:

    struct SearchRequest {
      1: string key,
      2: string url
    }
    struct SearchResult {
      1: string key,
      2: string url,
      3: float score
    }
    struct SearchResponse {
      1: list<SearchResult> results,
      2: bool success,
      3: string message
    }
    service SearchEngine {
      SearchResponse search(1: SearchRequest request)
    }

#### Thrift Server
Then the C++ service would look something like this:

```cpp
class SearchEngine : virtual public SearchEngineIf {
 public:
  SearchEngine() {
    // Initialization.
  }

  void search(SearchResponse& response, const SearchRequest request) {
    // Your implementation goes here
    printf("search\n");
  }
};
```

#### Thrift Client
```python
# Make an object
request = SearchRequest(url="http://example.com/img.png")

# Talk to a server via TCP sockets, using a binary protocol
transport = TSocket.TSocket("localhost", 9090)
transport.open()
protocol = TBinaryProtocol.TBinaryProtocol(transport)

# Use the service we already defined
service = SearchEngine.Client(protocol)
response = service.search(request)

for result in response.results:
    print '%s, %s' (result.key, result.score)

```