// Whether to install a firmware image the update server offered. Kept apart from the download so it can be tested on a PC.
#pragma once

#include <stdbool.h>

typedef enum {
    UPDATE_INSTALL,
    UPDATE_SKIP_SAME_VERSION,
    UPDATE_REFUSE_WRONG_PROJECT,
    UPDATE_REFUSE_FAILED_BEFORE,
} update_decision_t;

// failed_version is the version this device already tried and rolled back from, or an empty string. pinned means
// someone asked for that one release by id, which is how to try a build again on purpose.
update_decision_t update_decide(const char *our_project, const char *our_version,
                                const char *new_project, const char *new_version,
                                const char *failed_version, bool pinned);
