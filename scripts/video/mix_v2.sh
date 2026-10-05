#!/bin/bash
# Video 2 audio (ffmpeg): VO (ElevenLabs) + music_bed_v2 & intro_music & cine/walk SFX ducked under VO via sidechaincompress, loudnorm -14 LUFS.
set -e
V=~/Documents/learning/mech-test/video; A=$V/audio; VO=$V/work/vo; O=$V/work/audio; R=~/Documents/learning/mech-test/blender/renders
d(){ python3 -c "print(int(round($1*1000)))"; }
S=(0 14 33 55 84 98 121 150 167); OFF=(3.0 0.8 0.8 0.8 0.8 0.8 0.8 0.8 0.8)
IN=""; F=""; L=""
for i in 0 1 2 3 4 5 6 7 8; do
  t=$(python3 -c "print(${S[$i]}+${OFF[$i]})"); IN="$IN -i $VO/vo_s$i.wav"
  F="$F[$i]aresample=48000,pan=stereo|c0=c0|c1=c0,adelay=$(d $t)|$(d $t)[vo$i];"; L="$L[vo$i]"
done
ffmpeg -v error -y $IN -i $A/music_bed_v2.wav -i $A/intro_music.wav -i $A/cine_mix.wav -i $R/mech_walk_v2_audio.wav \
 -filter_complex "$F
 ${L}amix=inputs=9:normalize=0,apad=whole_dur=184,atrim=0:184,volume=0dB[vob];
 [vob]asplit=2[vo][key];
 [9]atrim=0:172,afade=t=in:d=1.5,afade=t=out:st=168.5:d=3.5,volume=-5dB,adelay=$(d 12)|$(d 12)[bed];
 [10]afade=t=in:d=0.4,afade=t=out:st=11:d=4,volume=-5dB[intro];
 [11]asplit=5[c0][c1][c2][c3][c4];
 [c0]atrim=25.55:28.85,asetpts=PTS-STARTPTS,afade=t=out:st=2.7:d=0.6,volume=1dB[cA];
 [c1]atrim=16.4:19.2,asetpts=PTS-STARTPTS,afade=t=in:d=0.1,afade=t=out:st=2.5:d=0.3,volume=-6dB,adelay=$(d 126.4)|$(d 126.4)[cB];
 [c2]atrim=22.6:25.25,asetpts=PTS-STARTPTS,afade=t=in:d=0.1,afade=t=out:st=2.35:d=0.3,volume=-6dB,adelay=$(d 129.8)|$(d 129.8)[cC];
 [c3]atrim=25.55:28.55,asetpts=PTS-STARTPTS,afade=t=in:d=0.1,volume=-6dB,adelay=$(d 133.2)|$(d 133.2)[cD];
 [c4]atrim=28.25:31.15,asetpts=PTS-STARTPTS,afade=t=out:st=2.4:d=0.5,volume=-6dB,adelay=$(d 136.2)|$(d 136.2)[cE];
 [12]atrim=0:14,asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,afade=t=in:d=0.3,afade=t=out:st=13.3:d=0.7,volume=-4dB,adelay=$(d 84)|$(d 84)[walk];
 [bed][intro][cA][cB][cC][cD][cE][walk]amix=inputs=8:normalize=0:duration=longest,apad=whole_dur=184,atrim=0:184[under];
 [under][key]sidechaincompress=threshold=0.05:ratio=4:attack=40:release=500:makeup=1,asplit=2[ducked][stem];
 [vo][ducked]amix=inputs=2:normalize=0,afade=t=out:st=182:d=2[out]" \
 -map "[out]" -ar 48000 -c:a pcm_s24le $O/v2_premix.wav -map "[stem]" -ar 48000 $O/v2_under_stem.wav
I=$(ffmpeg -nostats -i $O/v2_premix.wav -filter_complex ebur128 -f null - 2>&1 | grep -E "^\s+I:" | tail -1 | awk '{print $2}')
G=$(python3 -c "print(-14.0-($I)+0.3)")
ffmpeg -v error -y -i $O/v2_premix.wav -af "volume=${G}dB,alimiter=limit=0.84:level=false:attack=3:release=60" -ar 48000 -c:a pcm_s24le $O/v2_mix.wav
ffmpeg -nostats -i $O/v2_mix.wav -filter_complex ebur128=peak=true -f null - 2>&1 | grep -A14 Summary | grep -E "I:|LRA:|Peak:"
