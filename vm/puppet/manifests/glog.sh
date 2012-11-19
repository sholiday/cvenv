#! /bin/sh
set -e
DOWNLOAD="http://google-glog.googlecode.com/files/"
NAME="glog-0.3.2"
ARCHIVE="$NAME.tar.gz"
DOWNLOADS="/tmp/downloads/glog"

mkdir -p $DOWNLOADS

cd $DOWNLOADS
wget -q "$DOWNLOAD/$ARCHIVE" -O $ARCHIVE
tar -xzf $ARCHIVE
cd $NAME

./configure
make
make install

rm -Rf $DOWNLOADS

ldconfig

exit 0