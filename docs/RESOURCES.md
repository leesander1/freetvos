# Memory, CPU, and how much RAM a box needs

Measured in the arm64 VM on an Apple Silicon Mac, four cores, at 4 GB, 3 GB and
2 GB of RAM, with `tools/measure.py`. Each figure is taken after the scenario has
settled: memory as the kernel reports it, CPU as the share of all four cores that
was busy over five seconds, and each part's share of memory counted so that
libraries two processes share are not counted twice.

```bash
RAM=2048 tools/run-qemu.sh
python3 tools/measure.py "idle home screen"
```

## The short answer

**4 GB if you are choosing a box. 3 GB runs everything comfortably. 2 GB is the
floor, and only with the swap in memory the image now turns on.**

- At 3 GB, every scenario here, split view with two services under all three
  ticker bars included, ran with no measurable time spent waiting on memory.
- At 2 GB one service at a time is fine. Split view and picture in picture work,
  but pack more than a gigabyte into swap and keep the processor busy doing it.
- 4 GB is the recommendation for real hardware rather than the minimum, because
  on most boxes the GPU's memory comes out of the same RAM (see below).

The processor matters less than having a GPU that works. With none, as in the
VM, drawing two services side by side took more than two cores of a fast Mac
chip. That is the compositor's work, and it is exactly what a GPU takes away.

## Two things about the VM that move these numbers

**There is no GPU.** Everything on screen, the home screen, the tickers, and every
frame of video, is drawn by the processor. On a box with a real GPU the CPU
figures below fall a long way, and a video decoded in hardware costs very little.
Treat them as the worst case.

**Memory goes the other way.** On most small ARM boards and cheap x86 boxes the
GPU has no memory of its own and takes it from the same RAM. A real 2 GB box
therefore has somewhat less for everything else than a 2 GB VM does.

## Where the memory goes

Idle, at 4 GB:

| Part | MB |
|---|---|
| Plasma shell, the home screen | 445 |
| Plasma's on-screen keyboard | 248 |
| KWin, the compositor, with Xwayland | 290 |
| Everything else: portals, kded, the AirPlay receiver, power tuning, systemd | about 650 |
| FreeTVOS's own services | 50–60 |
| Audio | 30–45 |

On top of that, while in use:

| Adding | MB | CPU |
|---|---|---|
| All three ticker bars | about 230 | a quarter of the four cores, drawn with no GPU |
| One streaming service | about 450 | |
| A second, for split view | about 430 more | see below |
| Live TV playing | 130 to 275 for the player | |
| Tuner support switched on | 20 to 40 | |

The on-screen keyboard is the largest single thing that is not in use. It has
never been seen to draw in the VM, and every page in FreeTVOS types through its
own keyboard instead. It stays, because a streaming service's sign-in page has
no other keyboard, and on hardware with a GPU it may well work. Removing it is
the first thing to try on a box that is short of memory.

## At 4 GB, no swap

| Scenario | Used | Available | CPU |
|---|---|---|---|
| Idle home screen | 1852 | 2031 | 0% |
| All three bars on | 2084 | 1799 | 24% |
| Bars, and YouTube open | 2365 | 1518 | 24% |
| Bars, and split view with YouTube and ESPN+ | 2845 | 1038 | 31% |
| Bars, and Live TV playing | 2222 | 1661 | 30% |
| The same, with tuner support on | 2260 | 1623 | 30% |

Room to spare in everything. Idle uses more here than at 2 GB for the same work,
because with memory to spare nothing is pushed out of it.

## At 3 GB, with swap in memory

| Scenario | Used | Available | Swapped | CPU |
|---|---|---|---|---|
| Idle home screen | 1777 | 1161 | 0 | 0% |
| All three bars on | 1992 | 946 | 0 | 31% |
| Bars, and YouTube open | 2179 | 759 | 129 | 30% |
| Bars, and split view with YouTube and ESPN+ | 2158 | 780 | 688 | 84% |
| Bars, and Live TV playing | 1684 | 1254 | 656 | 29% |
| The same, with tuner support on | 1704 | 1234 | 656 | 29% |

Time spent waiting on memory never reached a quarter of a percent. Split view
packs about 700 MB away, half what it does at 2 GB. Live TV was measured after
split view, which is why swap still holds what split view put there: nothing
needed it back.

## Where the processor goes

Sampled with `top` in split view at 3 GB, as a share of one core:

| Process | CPU |
|---|---|
| KWin, drawing both windows | 231% |
| The ticker bars | 64% |
| Plasma shell | 1% |
| Chromium, all of it | under 2% |

Neither service was playing video, so this is the cost of putting two windows
and three moving bars on screen with no GPU. With Live TV playing it was KWin at
55% and the bars at 60%, with the player itself barely registering: the test
channels are simple patterns, and a real HD broadcast decoded without hardware
help costs far more.

The ticker bars are the one part of FreeTVOS that costs processor time while
nothing else is happening, because they never stop moving. Switch them off and
idle is idle.

The 4 GB split view figure, 31%, is lower than every later run's 84 to 88%. It
was measured on the image before this one, and which layout was actually on
screen then was not checked, so trust the later figures.

## At 2 GB, before swap was added

| Scenario | Used | Available | CPU |
|---|---|---|---|
| Idle home screen | 1393 | 544 | 0% |
| All three bars on | 1590 | 347 | 31% |
| Bars, and YouTube open | 1817 | 120 | 74% |
| Bars, and split view with YouTube and ESPN+ | stalled | 98 | |

One service worked, with the machine already spending a tenth of its time
waiting on memory. Opening a second for split view stalled it: a load of 18,
everything waiting on memory a fifth of the time, the screen no longer drawing,
and the measurement itself unable to finish in a minute. Nothing was killed. The
kernel kept throwing out program code and reading it back in rather than giving
up on anything, which from a sofa looks like a television that has frozen.

The image had no swap at all. Fedora's swap-in-memory generator was installed
without the file that turns it on.

## At 2 GB, with swap in memory

The image now turns on zram: swap kept in RAM, compressed to around a third of
its size. Pages nobody is using are packed away rather than the kernel choosing
between freezing and killing. The setting lives in
`/usr/lib/systemd/zram-generator.conf`, and a freshly built disk comes up with
1.9 GB of it at 2 GB of RAM, with nothing in `/etc`.

| Scenario | Used | Available | Swapped | CPU |
|---|---|---|---|---|
| Idle home screen | 1251 | 686 | 401 | 0% |
| All three bars on | 1462 | 475 | 409 | 30% |
| Bars, and YouTube open | 1263 | 674 | 938 | 33% |
| Bars, and split view with YouTube and ESPN+ | 1423 | 514 | 1353 | 88% |
| Bars, and Live TV playing | 1408 | 529 | 600 | 24% |
| The same, with tuner support on | 1412 | 525 | 625 | 24% |

The Live TV rows come from a fresh start of the rebuilt image rather than
straight after split view, so what is in swap there is what the session packs
away by itself.

Everything ran and nothing was killed, and time spent waiting on memory stayed
under one percent throughout. Split view is where it shows: more than a
gigabyte is packed away, the processor is nearly flat out between drawing two
services and compressing memory, and going back to the home screen means
unpacking the parts of it that were put away.
