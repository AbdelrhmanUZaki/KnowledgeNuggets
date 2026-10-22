/* unlock-session.c -- release a Wayland session that river left locked.
 *
 * WHY THIS EXISTS
 * ---------------
 * river's LockManager.handleDestroy() (river/LockManager.zig) does not leave
 * the ".locked" state when the lock client dies:
 *
 *     fn handleDestroy(...) void {
 *         manager.lock = null;
 *         if (manager.state == .waiting_for_lock_surfaces) { ... }
 *     }                       <-- no unlock when the state is already .locked
 *
 * So if a locker is killed while the screen is locked, the session stays
 * locked for good: black screen, mouse cursor only, no way out (a VT switch
 * does not help, because the state lives in the compositor).
 *
 * The protocol itself allows a recovery path -- "compositors may also allow a
 * secure way to recover the session" -- and river implements it: a *new* lock
 * client is accepted even when the session is already locked, it gets the
 * "locked" event straight away, and it can then send "unlock_and_destroy",
 * which is the only request that makes river leave the locked state.
 *
 * This program is that client: it asks for the lock, waits for "locked" and
 * immediately releases it.  It does not draw anything and does not ask for a
 * password -- it is a recovery tool, not a locker.
 *
 * Build (see unlock-session.sh, which does it for you):
 *   wayland-scanner client-header \
 *       /usr/share/wayland-protocols/staging/ext-session-lock/ext-session-lock-v1.xml \
 *       ext-session-lock-v1-client-protocol.h
 *   wayland-scanner private-code \
 *       /usr/share/wayland-protocols/staging/ext-session-lock/ext-session-lock-v1.xml \
 *       ext-session-lock-v1-protocol.c
 *   gcc -o unlock-session unlock-session.c ext-session-lock-v1-protocol.c \
 *       $(pkg-config --cflags --libs wayland-client)
 */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <wayland-client.h>
#include "ext-session-lock-v1-client-protocol.h"

static struct wl_display *display;
static int got_locked = 0;
static int got_finished = 0;

static void handle_locked(void *data, struct ext_session_lock_v1 *lock)
{
	(void)data;
	printf("locked event received -> sending unlock_and_destroy\n");
	fflush(stdout);
	ext_session_lock_v1_unlock_and_destroy(lock);
	got_locked = 1;
	/* the protocol asks for a sync so the server really processes the
	 * unlock before we go away */
	wl_display_sync(display);
	wl_display_roundtrip(display);
}

static void handle_finished(void *data, struct ext_session_lock_v1 *lock)
{
	(void)data; (void)lock;
	printf("finished event received (the compositor refused the lock)\n");
	fflush(stdout);
	got_finished = 1;
}

static const struct ext_session_lock_v1_listener lock_listener = {
	.locked = handle_locked,
	.finished = handle_finished,
};

static void handle_global(void *data, struct wl_registry *registry, uint32_t name,
			  const char *interface, uint32_t version)
{
	(void)data;
	if (strcmp(interface, ext_session_lock_manager_v1_interface.name) != 0)
		return;
	struct ext_session_lock_manager_v1 *manager =
		wl_registry_bind(registry, name, &ext_session_lock_manager_v1_interface, 1);
	struct ext_session_lock_v1 *lock = ext_session_lock_manager_v1_lock(manager);
	ext_session_lock_v1_add_listener(lock, &lock_listener, NULL);
	printf("lock requested, waiting for the locked event\n");
	fflush(stdout);
}

static void handle_global_remove(void *data, struct wl_registry *registry, uint32_t name)
{
	(void)data; (void)registry; (void)name;
}

static const struct wl_registry_listener registry_listener = {
	.global = handle_global,
	.global_remove = handle_global_remove,
};

int main(void)
{
	display = wl_display_connect(NULL);
	if (!display) {
		fprintf(stderr, "cannot connect to the wayland display\n");
		return 1;
	}
	struct wl_registry *registry = wl_display_get_registry(display);
	wl_registry_add_listener(registry, &registry_listener, NULL);
	wl_display_roundtrip(display);   /* globals + send the lock request */
	wl_display_roundtrip(display);   /* the locked/finished event */
	wl_display_roundtrip(display);   /* flush the unlock */
	if (got_locked)
		printf("unlock_and_destroy sent\n");
	else if (got_finished)
		fprintf(stderr, "the compositor refused the lock request\n");
	else
		fprintf(stderr, "no event from the compositor\n");
	wl_display_disconnect(display);
	return got_locked ? 0 : 1;
}
