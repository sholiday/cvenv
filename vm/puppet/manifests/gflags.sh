#! /bin/sh
set -e
DOWNLOAD="http://gflags.googlecode.com/files/"
NAME="gflags-2.0"
ARCHIVE="$NAME.tar.gz"
DOWNLOADS="/tmp/downloads/gflags"

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