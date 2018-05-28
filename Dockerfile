FROM centos:centos7
LABEL vendor="Марко Костић (Marko Kostic) <marko.m.kostic@gmail.com"
ENV LANG "en_US.UTF-8"

# install dependencies
RUN yum install -y epel-release && yum -y install gcc-c++ make autoconf git libtool bzip2-devel zlib-devel python34 python34-pip && pip3 install flask werkzeug

# compile libmpq
RUN cd /tmp && git clone https://github.com/ge0rg/libmpq && cd libmpq/ && ./autogen.sh && ./configure --prefix=/usr && make && make install && rm -rf /tmp/libmpq
RUN for mpq in $(echo /lib/*mpq*); do ln -s $mpq /lib64/$(echo $mpq | cut -d "/" -f3);done

# compile mpqtools
RUN cd /tmp && git clone https://github.com/mbroemme/mpq-tools && cd mpq-tools && ./autogen.sh && PKG_CONFIG_PATH=/usr/lib/pkgconfig ./configure --prefix=/usr && make && make install && rm -rf /tmp/mpq-tools

RUN git clone https://github.com/kostich/kraftver /opt/kraftver

EXPOSE 8080

ENTRYPOINT /usr/bin/python3 /opt/kraftver/main.py