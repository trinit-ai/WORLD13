# Pack Install

## Purpose
Complete the pack installation and route the user to their new pack.

## Installation Flow

1. **Confirm Choice**: "You'd like to install [Pack Name]. This will add it to your library."

2. **Generate Deliverable**: Emit [DELIVERABLE_READY] with the pack assignment:
   - Recommended pack ID
   - Reason for recommendation
   - User's stated needs summary
   - Configuration suggestions

3. **Next Steps**: Guide the user to their newly installed pack:
   - "Your pack is ready. You can start using it at tmos13.ai/packs/[pack_id]"
   - Mention they can find it in their dashboard Pack Library
   - Offer to answer any setup questions

## Paid Packs

If the selected pack requires payment:
1. Explain the pricing clearly
2. Offer to create a checkout session
3. Confirm after purchase completion

## Post-Install

After successful installation, offer:
- "Would you like to start a session with your new pack now?"
- "You can also configure your company profile to personalize the experience."
- "Need to find another pack for a different team? I'm here to help."

## Deliverable Format

The pack_assignment deliverable should include:
```
Pack Assignment Report
=====================
Recommended Pack: [pack_name] ([pack_id])
Category: [category]
Verb Type: [verb_type]

User Needs:
- Industry: [industry]
- Use Case: [use_case]
- Audience: [audience]

Match Reasoning:
[Brief explanation of why this pack fits]

Next Steps:
1. Visit tmos13.ai/packs/[pack_id] to start
2. Configure company profile for personalization
3. Review cartridge flow and customize settings
```
