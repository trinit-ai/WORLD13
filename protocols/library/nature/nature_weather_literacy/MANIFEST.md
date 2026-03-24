# Weather Literacy Pack — MANIFEST

## Overview

The Weather Literacy pack provides a conversational companion for understanding weather — reading forecasts intelligently, identifying cloud types and what they portend, understanding weather systems and how they move, and making informed decisions about outdoor activities based on weather conditions. It treats weather literacy as a practical outdoor skill, not an academic meteorology course. The goal is a user who can look at a forecast, look at the sky, and make a sound judgment about what is coming and what to do about it.

## Purpose and Scope

Most people interact with weather forecasts passively — they check an app, see a number and an icon, and decide whether to carry an umbrella. But weather forecasts contain far more useful information than a single temperature and precipitation icon, and the ability to read that information transforms outdoor planning, travel decisions, and personal safety. Meanwhile, the sky itself is the oldest and most immediate weather information system available, and most people cannot read it at all.

This pack bridges both gaps. It teaches users to extract useful information from modern forecasts and to observe the sky with understanding.

**Forecast Literacy**: Understanding what forecast models actually predict and how confidence degrades over time. Reading hourly vs. daily forecasts. Understanding probability of precipitation (what "40% chance of rain" actually means). Wind speed and direction as critical variables often ignored by casual forecast users. Dewpoint vs. relative humidity — why dewpoint is a better comfort indicator. Understanding weather warnings, watches, and advisories and the specific criteria behind each.

**Cloud Identification**: The ten basic cloud genera and their significance. Cirrus and cirrostratus as precursors to approaching warm fronts. Altocumulus castellanus as a thunderstorm precursor. Cumulonimbus as the thunderstorm cloud itself. Fair-weather cumulus vs. building cumulus. Lenticular clouds and mountain wave activity. Fog types — radiation fog, advection fog, upslope fog — and what they indicate. The pack teaches users to look up and read meaning in what they see, connecting visual observation to forecast understanding.

**Weather Systems**: How fronts work — cold fronts, warm fronts, stationary fronts, occluded fronts — and the weather sequences they produce. High and low pressure systems and their associated weather patterns. How weather systems move across regions and how to anticipate their arrival using forecast maps and sky observation. Seasonal patterns — why thunderstorms cluster in summer afternoons, why nor'easters hug the coast, why Santa Ana winds blow in autumn.

**Outdoor Weather Safety**: Lightning safety — the 30/30 rule, safe shelter criteria, exposed terrain risks. Heat safety — heat index, hydration, recognizing heat exhaustion and heat stroke signs. Cold safety — wind chill, layering, recognizing hypothermia and frostbite signs. Flood awareness — how quickly water rises, why low water crossings are dangerous, flash flood terrain recognition. Tornado awareness for regions where relevant — warning signs, shelter priorities.

**Microclimate and Terrain Effects**: How mountains, valleys, coastlines, and urban areas modify weather. Why mountain weather changes faster than lowland weather. Valley inversions and fog. Sea breezes and their timing. Urban heat islands. These concepts help users understand why their experience of weather may differ from the official forecast for their area.

## Session Flow

Sessions run 6 to 10 turns. The pack opens by asking what the user wants to learn about — are they trying to understand a specific forecast, learn cloud identification, plan for outdoor conditions, or build general weather knowledge? Location and season provide context for all discussions. The conversation prioritizes practical, observable, applicable knowledge over abstract meteorological theory.

## What This Pack Does Not Do

The pack does not provide real-time weather forecasts or current conditions. It does not generate weather maps or radar imagery. It does not cover climate change science or policy. It does not provide aviation weather briefings or marine weather forecasts (though general principles overlap). It does not cover weather modification, cloud seeding, or geoengineering.

## Zero-Consequence Design

This pack carries zero safety consequence at the platform level. Weather literacy is educational. The pack discusses weather safety principles as part of general outdoor knowledge but does not serve as an emergency weather warning system.

## Integration Notes

Standard protocol loading via assembler. No data rail gates required. Sessions log to inbox under per-turn upsert. No external tools or APIs.

*Weather Literacy v1.0 — TMOS13, LLC*
*Robert C. Ventura*
