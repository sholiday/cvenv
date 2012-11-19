# Read more about puppet here:
# http://docs.puppetlabs.com/guides/language_guide.html

import "common.pp"
include users
include development

file {"/cvenv":
  ensure => directory,
  require => User["cvenv"],
  owner => "cvenv",
  group => "cvenv",
}

file {"/mnt/data":
  ensure => directory,
  require => User["cvenv"],
  owner => "cvenv",
  group => "cvenv",
}

file {"/cvenv/data":
  ensure => link,
  target => "/mnt/data",
  require => [User["cvenv"],
              File["/mnt/data"],
              File["/cvenv"],
             ],
  owner => "cvenv",
  group => "cvenv",
}