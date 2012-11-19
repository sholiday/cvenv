class users {

  notice("Users")

  user { "cvenv":
    ensure => present,
    groups => ["sudo", "plugdev", "admin"],
    shell => "/bin/bash",
    managehome => true,
  }

  file { "/home/cvenv/.ssh":
    ensure => "directory",
    mode => 0600,
    owner => "cvenv"
  }

  file {'/home/cvenv/.bashrc':
    source => "/etc/puppet/files/bashrc",
    owner => "cvenv",
    group => "cvenv",
    require => User["cvenv"],
  }

  file {'/home/cvenv/.ssh/authorized_keys':
    source => "/etc/puppet/files/authorized_keys",
    require => [File["/home/cvenv/.ssh"], User["cvenv"]],
    mode => 0600,
    owner => "cvenv"
  }
  
  file {'/home/cvenv/.ssh/id_rsa':
      source => "/etc/puppet/files/id_rsa",
      require => [File["/home/cvenv/.ssh"], User["cvenv"]],
      mode => 0600,
      owner => "cvenv"
    }
    
  group { "puppet":
    ensure => "present",
  }

  file { '/etc/motd':
    source => "/etc/puppet/files/motd",
  }
}