import discord
import os
import subprocess
import math
import shutil
import re
from dotenv import load_dotenv

load_dotenv()

class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.search_results = {}

    async def on_ready(self):
        print(f"We have logged in as {self.user}")

    async def on_message(self, message):
        if message.author == self.user:
            return

        print(f"Received message: {message.content} from {message.author}")

        if message.content.startswith("$search"):
            # Extract the search terms from the message content
            _, *search_terms = message.content.split(" ")
            show_name = " ".join(search_terms)

            # Execute get_iplayer command to search for TV shows
            get_iplayer_cmd = [
                "C:\\Program Files\\get_iplayer\\get_iplayer.cmd",
                "--type=tv",
                "--search",
                show_name,
            ]
            output = (
                subprocess.run(get_iplayer_cmd, stdout=subprocess.PIPE)
                .stdout.decode()
                .split("Matches:", 1)[-1]
            )
            results = output.split("\n")[1:-1]

            # Store search results for the user
            self.search_results[message.author.id] = [
                (
                    line.split(",")[-1].strip(),
                    "-" not in line.split(" - ")[1],
                )
                if " - " in line
                else (line.split(",")[-1].strip(), False)
                for line in results
            ]

            # Display search results to the user
            await message.channel.send(
                "Choose an episode or film to download by number:\n"
                + "\n".join(f"{i+1}: {line}" for i, line in enumerate(results))
            )

            # Wait for the user's response
            response = await self.wait_for_response(message.author)
            if response:
                index = int(response.content) - 1
                chosen_episode, is_tv_show = self.search_results[message.author.id][index]
                media_type = "TV Show" if is_tv_show else "Film"

                # Assign output_dir here based on media type
                output_dir = "D:\\TV Shows" if is_tv_show else "D:\\Films"

                media_name, runtime, _ = await self.get_info(chosen_episode, message)
                await self.download(message.channel, media_type, chosen_episode, media_name, runtime, output_dir, firstbcastyear)

        elif message.content.startswith("$download"):
            # Extract the index from the message content
            _, index = message.content.split(" ", 1)
            index = int(index) - 1
            chosen_episode, is_tv_show = self.search_results[message.author.id][index]
            media_type = "TV Show" if is_tv_show else "Film"

            # Assign output_dir here based on media type
            output_dir = "D:\\TV Shows" if is_tv_show else "D:\\Films"

            media_name, runtime, _ = await self.get_info(chosen_episode, message)
            await self.download(message.channel, media_type, chosen_episode, media_name, runtime, output_dir, firstbcastyear)

        elif message.content.startswith("$info"):
            # Extract the PID from the message content
            _, pid = message.content.split(" ", 1)
            await message.channel.send("Retrieving...")
            media_name, runtime, series, episodeshort, episodenum, output_dir, firstbcastyear = await self.get_info(pid, message)
            if media_name and runtime:
                media_type = "TV Show" if series else "Film"
                if series:
                    await message.channel.send(f"Series: {series}")
                if episodenum and episodeshort:
                    await message.channel.send(f"Episode: {episodenum} - {episodeshort}")
                await message.channel.send(f"Title: {media_name}\nRuntime: {runtime} minutes\nType: {media_type}")

        elif message.content.startswith("$get"):
            # Extract the PID from the message content
            _, pid = message.content.split(" ", 1)
            await message.channel.send("Retrieving...")
            media_name, runtime, series, episodeshort, episodenum, output_dir, firstbcastyear = await self.get_info(pid, message)
            if media_name and runtime:
                media_type = "TV Show" if series else "Film"
                if series:
                    await message.channel.send(f"Series: {series}")
                if episodenum and episodeshort:
                    await message.channel.send(f"Episode: {episodenum.lstrip()} - {episodeshort}")
                await self.download(message.channel, media_type, pid, media_name, runtime, output_dir, firstbcastyear)

    async def get_info(self, pid, message):
        # Execute get_iplayer command to get media information
        get_info_cmd = [
            "C:\\Program Files\\get_iplayer\\get_iplayer.cmd",
            "--info",
            "--pid=" + pid,
        ]
        process = subprocess.run(get_info_cmd, stdout=subprocess.PIPE)
        output = process.stdout.decode()

        media_name = ""
        runtime = ""
        series = ""
        episodeshort = ""
        episodenum = ""
        firstbcastyear = ""

        lines = output.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("brand:"):
                series = line.strip().split(": ", 1)[-1]
            elif line.startswith("episodeshort:"):
                episodeshort = line.strip().split(": ", 1)[-1]
            elif line.startswith("episodenum:"):
                episodenum = line.strip().split(": ", 1)[-1]
            elif line.startswith("name:"):
                media_name = line.strip().split(": ", 1)[-1]
            elif line.startswith("runtime:"):
                runtime = line.strip().split(": ", 1)[-1]
            elif line.startswith("firstbcastyear:"):
                firstbcastyear = line.strip().split(": ", 1)[-1]

        # Determine output_dir based on the presence of series
        output_dir = "D:\\TV Shows" if series else "D:\\Films"

        return media_name.lstrip(), runtime.lstrip(), series.lstrip(), episodeshort.lstrip(), episodenum.lstrip(), output_dir, firstbcastyear

    async def download(self, channel, media_type, pid, media_name, runtime, output_dir, firstbcastyear):
        await channel.send(f"Download started: {media_type}: {media_name} (Runtime: {runtime} minutes)")

        # Determine the file prefix based on the media type and first broadcast year
        if media_type == "Film":
            file_prefix = f"{media_name} ({firstbcastyear})"
        else:
            brand, _, series_number, episode_name, episode_number, _, firstbcastyear = await self.get_info(pid, "")
            file_prefix = f"{brand} - {series_number}, {episode_number} - {episode_name}"

        # Replace unsupported characters in the file prefix
        file_prefix = re.sub(r'[<>:"/\\|?*]', '', file_prefix)

        # Calculate estimated download time based on 6 Mbps bitrate and 40 Mbps internet speed
        download_size_mb = 6 * (float(runtime) / 60)
        download_time_seconds = (download_size_mb / 40) * 8  # Convert to seconds

        # Calculate processing time as 40% of download time
        processing_time_seconds = 0.4 * download_time_seconds

        # Calculate total time including processing time
        total_time_seconds = download_time_seconds + processing_time_seconds

        # Display ETA before running the download command
        eta = self.format_time(total_time_seconds)
        await channel.send(f"Estimated time: {eta}")

        get_iplayer_cmd = [
            "C:\\Program Files\\get_iplayer\\get_iplayer.cmd",
            "--pid",
            pid,
            "--get",
            "--output",
            output_dir,
            "--tv-quality=fhd",
            "--force",
            '--file-prefix=' + file_prefix,
        ]

        process = subprocess.run(get_iplayer_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = process.stdout.decode()
        errors = process.stderr.decode()

        print("Console output:", output)
        if errors:
            print("Errors:", errors)

        await channel.send(
            f"Downloaded {media_type}: {media_name} (Runtime: {runtime} minutes) to '{output_dir}' directory"
        )

    async def wait_for_response(self, author):
        def check(message):
            return message.author == author
        try:
            response = await self.wait_for("message", check=check, timeout=60)
        except asyncio.TimeoutError:
            return None
        else:
            return response

    def format_time(self, minutes):
        minutes = int(minutes)
        hours = minutes // 60
        minutes %= 60
        return f"{hours}h {minutes}m"

intents = discord.Intents.all()
client = MyClient(intents=intents)
client.run(os.getenv('DISCORD_TOKEN'))