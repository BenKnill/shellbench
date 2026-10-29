// The environment every shellbench subject runs in (the GNU oracle uses the same values).
export const MTIME = new Date("2026-10-01T12:00:00Z");
export const HOME = "/home/user";
export const CWD = "/home/user/work";
export const ROOTS = [HOME, "/tmp"];
export const ENV = {
  HOME, USER: "user", LOGNAME: "user", PATH: "/opt/gnubin:/usr/local/bin:/usr/bin:/bin",
  LC_ALL: "C.UTF-8", LANG: "C.UTF-8", TZ: "UTC", SHELL: "/bin/bash", TERM: "dumb",
};
