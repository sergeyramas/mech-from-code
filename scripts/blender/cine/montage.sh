#!/bin/zsh
# montage.sh out.jpg img1 img2 ... (grid of 2 columns, each scaled to 640 wide)
out=$1; shift
n=$#; args=(); i=0; lay=()
for f in "$@"; do args+=(-i $f); done
cols=2
filt=""
for ((k=0;k<n;k++)); do filt+="[$k]scale=640:-2[s$k];"; x=$((k%cols)); y=$((k/cols)); lay+=("$((x*640))_$((y*360))"); done
ins=""; for ((k=0;k<n;k++)); do ins+="[s$k]"; done
if (( n==1 )); then cp $1 $out; exit; fi
ffmpeg -y -loglevel error "${args[@]}" -filter_complex "${filt}${ins}xstack=inputs=${n}:layout=${(j:|:)lay}:fill=black[o]" -map "[o]" -frames:v 1 -q:v 3 $out
