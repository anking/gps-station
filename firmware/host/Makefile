# Builds and tests the portable firmware core on a PC. The firmware itself builds with PlatformIO, see ../readme.md.
CC ?= gcc
CFLAGS ?= -std=gnu11 -O1 -g -Wall -Wextra -Wno-format-truncation -fsanitize=address,undefined -fno-omit-frame-pointer
CORE := ../src/core/base_station.c ../src/core/caster.c ../src/core/direct_server.c ../src/core/fixed_position.c ../src/core/gnss_stream.c ../src/core/update_policy.c
HEADERS := $(wildcard ../src/core/*.h)

.PHONY: all test e2e clean

all: base_host core_tests

base_host: base_host.c $(CORE) $(HEADERS)
	$(CC) $(CFLAGS) -o $@ base_host.c $(CORE)

core_tests: core_tests.c $(CORE) $(HEADERS)
	$(CC) $(CFLAGS) -o $@ core_tests.c $(CORE)

test: core_tests
	./core_tests

e2e: base_host
	python3 e2e.py ./base_host

clean:
	rm -f base_host core_tests
