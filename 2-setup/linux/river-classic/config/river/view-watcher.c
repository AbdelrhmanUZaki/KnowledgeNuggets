// view-watcher — per-workspace gap/border policy for river-classic
//
// river has no "how many views are visible" CLI, but its status protocol does:
// each output sends `view_tags` (a 32-bit tag mask per view) and `focused_tags`.
// This small client counts the views that intersect the focused tags and keeps
// two things in sync:
//
//   one visible view  -> border-width 0  (rivertile's patch already makes the
//                        layout edge-to-edge with no gaps)
//   two or more       -> border-width 2  (rivertile applies 12 px view gaps and
//                        no outer padding)
//
// It invokes riverctl (the same commands a user would run), so it works with
// the stock rivertile and needs no compositor changes.
//
// Built and started by view-watcher.sh; killed by session-cleanup.sh.

#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#include <wayland-client.h>

#include "river-status-unstable-v1-client-protocol.h"


struct output {
    struct wl_output *wl_output;
    struct zriver_output_status_v1 *status;
    uint32_t focused_tags;
    uint32_t *view_tags;
    size_t n_view_tags;
    struct output *next;
};

static struct wl_display *display;
static struct wl_registry *registry;
static struct zriver_status_manager_v1 *status_manager;
static struct output *outputs;
static int last_multi = -1; /* -1 unknown, 0 single, 1 multi */
static int pending = 0;
static char riverctl_path[4096] = "riverctl";

static void resolve_riverctl(void) {
    const char *home = getenv("HOME");
    if (home) {
        snprintf(riverctl_path, sizeof(riverctl_path), "%s/.local/bin/riverctl", home);
        if (access(riverctl_path, X_OK) == 0)
            return;
    }
    snprintf(riverctl_path, sizeof(riverctl_path), "/usr/bin/riverctl");
    if (access(riverctl_path, X_OK) == 0)
        return;
    snprintf(riverctl_path, sizeof(riverctl_path), "/usr/local/bin/riverctl");
}

static void run(char *const argv[]) {
    pid_t pid = fork();
    if (pid == 0) {
        execvp(argv[0], argv);
        _exit(127);
    } else if (pid > 0) {
        int status;
        while (waitpid(pid, &status, 0) < 0) {
        }
    }
}

static int visible_views(void) {
    int n = 0;
    for (struct output *o = outputs; o; o = o->next) {
        for (size_t i = 0; i < o->n_view_tags; i++) {
            if (o->view_tags[i] & o->focused_tags)
                n++;
        }
    }
    return n;
}

static void apply(void) {
    int n = visible_views();
    int multi = n > 1;
    if (multi == last_multi)
        return;
    last_multi = multi;
    fprintf(stderr, "view-watcher: %d visible -> border %d\n",
            n, multi ? 2 : 0);

    if (multi)
        run((char *const[]){ riverctl_path, "border-width", "2", NULL });
    else
        run((char *const[]){ riverctl_path, "border-width", "0", NULL });
}

static void output_focused_tags(void *data, struct zriver_output_status_v1 *s,
                                uint32_t tags) {
    (void)s;
    ((struct output *)data)->focused_tags = tags;
    pending = 1;
}

static void output_view_tags(void *data, struct zriver_output_status_v1 *s,
                             struct wl_array *tags) {
    (void)s;
    struct output *o = data;
    free(o->view_tags);
    o->n_view_tags = tags->size / sizeof(uint32_t);
    o->view_tags = malloc(tags->size ? tags->size : sizeof(uint32_t));
    if (o->view_tags && tags->size)
        memcpy(o->view_tags, tags->data, tags->size);
    pending = 1;
}

static const struct zriver_output_status_v1_listener status_listener = {
    .focused_tags = output_focused_tags,
    .view_tags = output_view_tags,
};

static void attach_status(struct output *o) {
    if (!status_manager || o->status)
        return;
    o->status = zriver_status_manager_v1_get_river_output_status(
        status_manager, o->wl_output);
    zriver_output_status_v1_add_listener(o->status, &status_listener, o);
}

static void registry_global(void *data, struct wl_registry *reg, uint32_t name,
                            const char *interface, uint32_t version) {
    (void)data;
    if (strcmp(interface, wl_output_interface.name) == 0) {
        struct output *o = calloc(1, sizeof(*o));
        if (!o)
            return;
        o->wl_output = wl_registry_bind(reg, name, &wl_output_interface,
                                        version < 4 ? version : 4);
        o->next = outputs;
        outputs = o;
        attach_status(o);
    } else if (strcmp(interface, zriver_status_manager_v1_interface.name) == 0) {
        status_manager = wl_registry_bind(
            reg, name, &zriver_status_manager_v1_interface, 1);
        for (struct output *o = outputs; o; o = o->next)
            attach_status(o);
    }
}

static void registry_global_remove(void *data, struct wl_registry *reg,
                                   uint32_t name) {
    (void)data;
    (void)reg;
    (void)name; /* outputs are not expected to disappear mid-session */
}

static const struct wl_registry_listener registry_listener = {
    .global = registry_global,
    .global_remove = registry_global_remove,
};

int main(void) {
    resolve_riverctl();
    display = wl_display_connect(NULL);
    if (!display) {
        fprintf(stderr, "view-watcher: cannot connect to the compositor\n");
        return 1;
    }
    registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &registry_listener, NULL);

    /* First roundtrip: globals. Second: initial focused_tags/view_tags. */
    wl_display_roundtrip(display);
    wl_display_roundtrip(display);
    apply();

    while (wl_display_dispatch(display) != -1) {
        if (pending) {
            pending = 0;
            apply();
        }
    }
    return 0;
}
