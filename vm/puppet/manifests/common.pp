Exec {
  logoutput => on_failure,
  path => ["/bin", "/sbin", "/usr/bin", "/usr/sbin",
           "/usr/local/bin",  "/usr/local/sbin"]
}
File { owner => 0, group => 0, mode => 0644 }

file {'/etc/sudoers.d/sudoers':
  source => "/etc/puppet/files/sudoers",
  mode => 0440,
}

Exec["apt-update"] -> Package <| |>
exec { "apt-update":
  command => "/usr/bin/apt-get update"
}
