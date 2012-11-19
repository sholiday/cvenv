#! /bin/sh
set -e
DOWNLOAD="http://downloads.sourceforge.net/project/opencvlibrary/opencv-unix/2.4.0/OpenCV-2.4.0.tar.bz2?r=http%3A%2F%2Fopencv.org%2Fdownloads.html&ts=1347476247&use_mirror=hivelocity"
NAME="OpenCV-2.4.0"
ARCHIVE="$NAME.tar.bz2"
DOWNLOADS="/tmp/downloads/opencv"

mkdir -p $DOWNLOADS

cd $DOWNLOADS
wget -q $DOWNLOAD -O $ARCHIVE
rm -Rf $NAME
tar -xjf $ARCHIVE
cd $NAME

mkdir build
cd build

cmake -D WITH_QT=ON -D WITH_XINE=ON -D WITH_OPENGL=ON -D WITH_TBB=ON -D BUILD_EXAMPLES=ON ..
make
make install

echo "/usr/local/lib" >> /etc/ld.so.conf
ldconfig

rm -Rf $DOWNLOADS
exit 0