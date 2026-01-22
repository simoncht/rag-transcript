"""
Performance test for download and transcription of a specific YouTube video.

This test diagnoses performance bottlenecks in the video processing pipeline.
Run with: docker compose exec app pytest tests/test_transcription_performance.py -v -s
"""
import os
import time
import tempfile
import pytest
from datetime import datetime

# Test video: 69.3 minutes long
TEST_VIDEO_URL = "https://www.youtube.com/watch?v=APdwwZQJJrI"
TEST_VIDEO_ID = "APdwwZQJJrI"


class TestTranscriptionPerformance:
    """Performance tests for the transcription pipeline."""

    @pytest.fixture
    def youtube_service(self):
        """Get YouTube service instance."""
        from app.services.youtube import YouTubeService
        return YouTubeService()

    @pytest.fixture
    def transcription_service(self):
        """Get transcription service instance."""
        from app.services.transcription import TranscriptionService
        return TranscriptionService()

    def test_get_video_info(self, youtube_service):
        """Test fetching video metadata (should be fast)."""
        print("\n" + "=" * 60)
        print("TEST: Video Info Fetch")
        print("=" * 60)

        start = time.time()
        info = youtube_service.get_video_info(TEST_VIDEO_URL)
        elapsed = time.time() - start

        print(f"Title: {info.get('title', 'N/A')}")
        print(f"Duration: {info.get('duration', 0)} seconds ({info.get('duration', 0) / 60:.1f} minutes)")
        print(f"Channel: {info.get('channel', 'N/A')}")
        print(f"Time to fetch info: {elapsed:.2f}s")

        assert info is not None
        assert elapsed < 30, f"Video info fetch took too long: {elapsed:.2f}s"

    def test_download_audio_only(self):
        """Test downloading audio (measure download speed separately)."""
        import subprocess

        print("\n" + "=" * 60)
        print("TEST: Audio Download Only")
        print("=" * 60)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "audio.mp3")

            start = time.time()
            result = subprocess.run([
                'yt-dlp',
                '-x',
                '--audio-format', 'mp3',
                '-o', output_path,
                TEST_VIDEO_URL
            ], capture_output=True, text=True)
            download_time = time.time() - start

            if result.returncode != 0:
                print(f"Download failed: {result.stderr}")
                pytest.fail(f"Download failed: {result.stderr}")

            file_size_mb = os.path.getsize(output_path) / (1024 * 1024) if os.path.exists(output_path) else 0

            print(f"Download time: {download_time:.2f}s ({download_time/60:.1f} min)")
            print(f"File size: {file_size_mb:.2f} MB")
            print(f"Download speed: {file_size_mb / download_time:.2f} MB/s" if download_time > 0 else "N/A")

            assert os.path.exists(output_path), "Audio file not created"
            # For a 60-min video, download should complete within 10 minutes
            assert download_time < 600, f"Download took too long: {download_time:.2f}s"

    def test_transcription_model_info(self, transcription_service):
        """Test and display transcription model configuration."""
        print("\n" + "=" * 60)
        print("TEST: Transcription Model Info")
        print("=" * 60)

        info = transcription_service.get_model_info()
        print(f"Model: {info.get('model', 'N/A')}")
        print(f"Device: {info.get('device', 'N/A')}")
        print(f"Backend: {info.get('backend', 'N/A')}")

        # Estimate transcription time based on model and device
        model = info.get('model', 'base')
        device = info.get('device', 'cpu')

        # Rough estimates for 60-min audio (real-time factor)
        rtf_estimates = {
            ('tiny', 'cpu'): 0.5,    # ~30 min for 60 min audio
            ('base', 'cpu'): 1.5,    # ~90 min for 60 min audio
            ('small', 'cpu'): 3.0,   # ~180 min for 60 min audio
            ('medium', 'cpu'): 6.0,  # ~360 min for 60 min audio
            ('large', 'cpu'): 12.0,  # ~720 min for 60 min audio
            ('tiny', 'cuda'): 0.05,  # ~3 min for 60 min audio
            ('base', 'cuda'): 0.1,   # ~6 min for 60 min audio
            ('small', 'cuda'): 0.2,  # ~12 min for 60 min audio
            ('medium', 'cuda'): 0.4, # ~24 min for 60 min audio
            ('large', 'cuda'): 0.8,  # ~48 min for 60 min audio
        }

        rtf = rtf_estimates.get((model, device), 2.0)
        estimated_time_min = 60.8 * rtf  # 60.8 min video

        print(f"\nEstimated transcription time for 60.8 min video:")
        print(f"  Real-time factor (RTF): ~{rtf}x")
        print(f"  Estimated time: ~{estimated_time_min:.0f} minutes ({estimated_time_min/60:.1f} hours)")

        if device == 'cpu' and model in ['medium', 'large']:
            print("\n⚠️  WARNING: Using large model on CPU will be VERY slow!")
            print("   Consider using 'tiny' or 'base' model, or switch to GPU.")

    @pytest.mark.slow
    def test_transcribe_short_sample(self, transcription_service):
        """
        Test transcription with a SHORT sample (first 60 seconds only).
        This gives an estimate without waiting for the full video.

        Run with: pytest tests/test_transcription_performance.py::TestTranscriptionPerformance::test_transcribe_short_sample -v -s
        """
        import subprocess

        print("\n" + "=" * 60)
        print("TEST: Transcribe Short Sample (19 seconds)")
        print("=" * 60)

        # Use a shorter video for quick testing
        short_test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # "Me at the zoo" - 19 seconds

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "audio.mp3")

            # Download using yt-dlp directly
            print("Downloading short test video...")
            start = time.time()
            result = subprocess.run([
                'yt-dlp',
                '-x',
                '--audio-format', 'mp3',
                '-o', audio_path,
                short_test_url
            ], capture_output=True, text=True)
            download_time = time.time() - start

            if result.returncode != 0:
                print(f"Download failed: {result.stderr}")
                pytest.skip("Download failed")

            print(f"Download time: {download_time:.2f}s")

            # Transcribe
            print("Transcribing...")
            start = time.time()
            transcript_result = transcription_service.transcribe_file(audio_path)
            transcribe_time = time.time() - start

            print(f"Transcription time: {transcribe_time:.2f}s")
            print(f"Audio duration: {transcript_result.duration_seconds:.2f}s")
            print(f"Real-time factor: {transcribe_time / transcript_result.duration_seconds:.2f}x")
            print(f"Word count: {transcript_result.word_count}")
            print(f"Text preview: {transcript_result.full_text[:200]}...")

            # Extrapolate for 60-min video
            rtf = transcribe_time / transcript_result.duration_seconds
            estimated_60min = rtf * 60.8 * 60  # 60.8 minutes in seconds
            print(f"\n📊 Extrapolated time for 60.8 min video: {estimated_60min/60:.1f} minutes ({estimated_60min/3600:.2f} hours)")

    @pytest.mark.slow
    def test_full_pipeline_with_timing(self, youtube_service, transcription_service):
        """
        Full pipeline test with detailed timing for the specific problematic video.

        WARNING: This test may take 1-2+ hours on CPU!

        Run with: pytest tests/test_transcription_performance.py::TestTranscriptionPerformance::test_full_pipeline_with_timing -v -s
        """
        import subprocess

        print("\n" + "=" * 60)
        print(f"TEST: Full Pipeline - {TEST_VIDEO_URL}")
        print(f"Started at: {datetime.now().isoformat()}")
        print("=" * 60)

        timings = {}

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "audio.mp3")

            # Step 1: Get video info
            print("\n[Step 1/3] Fetching video info...")
            start = time.time()
            info = youtube_service.get_video_info(TEST_VIDEO_URL)
            timings['video_info'] = time.time() - start
            print(f"  Title: {info.get('title', 'N/A')}")
            print(f"  Duration: {info.get('duration', 0)/60:.1f} minutes")
            print(f"  Time: {timings['video_info']:.2f}s")

            # Step 2: Download audio using yt-dlp directly
            print("\n[Step 2/3] Downloading audio...")
            start = time.time()
            result = subprocess.run([
                'yt-dlp',
                '-x',
                '--audio-format', 'mp3',
                '-o', audio_path,
                TEST_VIDEO_URL
            ], capture_output=True, text=True)
            timings['download'] = time.time() - start

            if result.returncode != 0:
                print(f"  Download failed: {result.stderr}")
                pytest.fail(f"Download failed: {result.stderr}")

            file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
            print(f"  File size: {file_size_mb:.2f} MB")
            print(f"  Time: {timings['download']:.2f}s ({timings['download']/60:.1f} min)")

            # Step 3: Transcribe
            print("\n[Step 3/3] Transcribing (this will take a while on CPU)...")
            print(f"  Started at: {datetime.now().isoformat()}")

            def progress_callback(status):
                print(f"  Progress: {status}")

            start = time.time()
            transcript_result = transcription_service.transcribe_file(audio_path, progress_callback=progress_callback)
            timings['transcription'] = time.time() - start

            print(f"  Completed at: {datetime.now().isoformat()}")
            print(f"  Time: {timings['transcription']:.2f}s ({timings['transcription']/60:.1f} min)")
            print(f"  Word count: {transcript_result.word_count}")
            print(f"  Segments: {len(transcript_result.segments)}")

            # Summary
            total_time = sum(timings.values())
            print("\n" + "=" * 60)
            print("TIMING SUMMARY")
            print("=" * 60)
            print(f"Video info:    {timings['video_info']:>8.2f}s")
            print(f"Download:      {timings['download']:>8.2f}s ({timings['download']/60:.1f} min)")
            print(f"Transcription: {timings['transcription']:>8.2f}s ({timings['transcription']/60:.1f} min)")
            print(f"─" * 30)
            print(f"TOTAL:         {total_time:>8.2f}s ({total_time/60:.1f} min)")
            print(f"\nReal-time factor: {timings['transcription'] / (info.get('duration', 3648)):.2f}x")

            # Assertions
            assert transcript_result.full_text, "No transcript text generated"
            assert transcript_result.word_count > 0, "No words in transcript"
