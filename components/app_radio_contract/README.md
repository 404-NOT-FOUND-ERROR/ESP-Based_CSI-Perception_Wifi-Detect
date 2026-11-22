# app_radio_contract

A header-only example contract for associated AP observations. It publishes no
Wi-Fi operation and owns no task or mutable state. The network owner fills the
snapshot; recorders consume a copied value under their caller's synchronization.

`app_network_link.h` retains its original include name for API compatibility.
`read_ms` is local API-read time; the age of the underlying driver measurement is
unknown. `sequence` counts read attempts, including failed ones. A network
generation identifies the associated connection context.

This standalone repository uses the `app_radio_contract` CMake dependency. When
integrating into an application that already owns `app_network_link.h`, use that
owner's public interface and adjust the dependency once; keep one authoritative
definition.
