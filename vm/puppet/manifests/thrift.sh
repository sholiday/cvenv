#! /bin/sh
set -e
DOWNLOAD="https://dist.apache.org/repos/dist/release/thrift/0.7.0/thrift-0.7.0.tar.gz"
NAME="thrift-0.7.0"
ARCHIVE="$NAME.tar.gz"
DOWNLOADS="/tmp/downloads/thrift"

mkdir -p $DOWNLOADS

cd $DOWNLOADS
wget -q $DOWNLOAD -O $ARCHIVE
rm -Rf $NAME
tar -xzf $ARCHIVE
cd $NAME

chmod +x configure
./configure --without-ruby
make
make install

echo "/usr/local/lib" >> /etc/ld.so.conf
ldconfig

rm -Rf $DOWNLOADS
exit 0