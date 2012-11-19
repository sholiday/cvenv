class development {
  package { [
    "ant",
    "autoconf",
    "automake",
    "bison",
    "build-essential",
    "checkinstall",
    "cmake",
    "ec2-ami-tools",
    "ec2-api-tools",
    "facter",
    "flex",
    "g++",
    "git",
    "google-mock",
    "htop",
    "language-pack-en",
    "libboost1.48-all-dev",
    "libcityhash-dev",
    "libcurl4-openssl-dev",
    "libevent-dev",
    "libgtest-dev",
    "libjasper-dev",
    "libjpeg8",
    "libjpeg8-dev",
    "libleveldb-dev",
    "libprotobuf-dev",
    "libsnappy-dev",
    "libsnappy1",
    "libssl-dev",
    "libtbb-dev",
    "libtiff4-dev",
    "libtool",
    "libxml2-dev",
    "libxslt1-dev",
    "pkg-config",
    "protobuf-compiler",
    "python",
    "python-cjson",
    "python-dev",
    "python-imaging",
    "python-numpy",
    "python-pip",
    "python-protobuf",
    "python-setuptools",
    "python-snappy",
    "python-sphinx",
    "s3cmd",
    "screen",
    "vim",
    "yasm",
    ]:
    ensure => "installed"
  }

  define install_pkg ($pkgname, $extra_easy_install_args = "",
                      $module_to_test_import) {
    exec {
     "InstallPkg_$pkgname":
     command => "easy_install-2.7 $extra_easy_install_args $pkgname",
     unless => "/usr/bin/python2.7 -c 'import $module_to_test_import'",
     require => Package["python-setuptools"];
    }
  }

  install_pkg {
    "boto":
    pkgname => "boto",
    module_to_test_import => "boto";
    
    "CherryPy":
    pkgname => "CherryPy",
    module_to_test_import => "cherrypy";

    "fabric":
    pkgname => "fabric",
    module_to_test_import => "fabric";

    "gflags":
    pkgname => "python-gflags",
    module_to_test_import => "gflags";

    "hashlib":
    pkgname => "hashlib",
    module_to_test_import => "hashlib";

    "python-dateutil":
    pkgname => "python-dateutil",
    module_to_test_import => "dateutil";

    "requests":
    pkgname => "requests",
    module_to_test_import => "requests";
    
    "virtualenv":
    pkgname => "virtualenv",
    module_to_test_import => "virtualenv";
  }

  Package <| |> -> Exec["glog"]
  exec {"glog":
    command => "bash glog.sh > /var/log/puppet-glog.log",
    creates => "/usr/local/include/glog/logging.h",
    # The library should be built with gflags to support --logtostderr.
    require => Exec["gflags"],
  }

  Package <| |> -> Exec["gflags"]
  exec {"gflags":
    command => "bash gflags.sh > /var/log/puppet-glfags.log",
    creates => "/usr/local/include/gflags/gflags.h"
  }

  Package <| |> -> Exec["opencv"]
  exec {"opencv":
    command => "bash opencv.sh > /var/log/puppet-opencv.log",
    creates => "/usr/local/include/opencv/cv.h",
    timeout => 0,
  }

  Package <| |> -> Exec["thrift"]
  exec {"thrift":
    command => "bash thrift.sh > /var/log/puppet-thrift.log",
    creates => "/usr/local/bin/thrift",
    timeout => 0,
  }
  
  file {"/etc/python2.7/sitecustomize.py":
    source => "/etc/puppet/files/sitecustomize.py",
    mode => 0644,
    require => Package["python"],
  }
}