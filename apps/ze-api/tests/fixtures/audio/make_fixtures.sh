#!/bin/sh
# Regenerates the audio fixtures. Needs ffmpeg with libopus.
set -eu
cd "$(dirname "$0")"
ffmpeg -v error -y -f lavfi -i sine=duration=3 -c:a libopus -f webm pipe:1 > stream.webm
ffmpeg -v error -y -f lavfi -i sine=duration=3 -c:a aac -movflags frag_keyframe+empty_moov -f mp4 pipe:1 > frag.mp4
ffmpeg -v error -y -f lavfi -i sine=duration=3 -c:a libopus -f ogg pipe:1 > stream.ogg
ffmpeg -v error -y -f lavfi -i sine=duration=1 -ar 16000 -ac 1 -c:a pcm_s16le -f wav pipe:1 > one_second.wav
