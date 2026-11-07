#include "update_policy.h"

#include <string.h>

update_decision_t update_decide(const char *our_project, const char *our_version,
                                const char *new_project, const char *new_version,
                                const char *failed_version, bool pinned)
{
    // Another device's firmware would boot and then never find its hardware, pinned or not
    if (strcmp(new_project, our_project) != 0) return UPDATE_REFUSE_WRONG_PROJECT;

    if (strcmp(new_version, our_version) == 0) return UPDATE_SKIP_SAME_VERSION;

    // Without this a release that crashes at startup installs, rolls back and installs again, forever
    if (!pinned && failed_version[0] != '\0' && strcmp(new_version, failed_version) == 0) return UPDATE_REFUSE_FAILED_BEFORE;

    return UPDATE_INSTALL;
}
