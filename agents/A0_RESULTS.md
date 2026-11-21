# A0 results (12:30)

- **Model:** `mistral-large-2512`, JSON mode, no reasoning. (`mistral-large-4` was 26-72 s per decision: see README.)
- **Valid leader JSON:** 10/10 sequential (retries used: 0). Median 3.1s, max 4.0s. Defied advice: 6/10.
- **8 parallel calls:** 8/8 OK, 4.1s wall (slowest 4.1s); rate-limited: 0.
- **call_reply latency:** median 1.4s over 3/3 lines (before TTS).

- **Managed Agents: NO-GO.** `mistralai-agents==1.1.0` (needs Python 3.12-3.14) with `mistral-large-4`: tool called and session memory works, but turn 1 took 9.6 s (budget 8 s) and it is a preview. With `mistral-large-2512` the tool was never called (it invented an offer). We keep chat completions with our own history.
- **Why not `mistral-large-4`:** reasoning cannot be turned off (`low` is the minimum). On the decide prompt it spent 1,800-2,500 thinking tokens: 26-72 s per call, often `finish_reason=length` with no text at 1,200-2,500 max_tokens. `python -m agents.probe` shows it.

## Samples

**ostrava** public: Ostrava offers Nordhaven a fair exchange: our oil for their chips. My soldiers need tools, not charity.  
private: Secure chips to modernize the army while keeping Nordhaven neutral before the Kessaria operation.  
action: {'type': 'propose_trade', 'by': 'ostrava', 'target': 'nordhaven', 'params': {'give': {'oil': 10}, 'get': {'chips': 10}}}; followed advice: True; reason: Advisers are correct—Nordhaven is the least hostile path to chips.

**zarnia** public: The People of Zarnia extend a hand of cooperation to Valdoria—let us trade oil for food, as equals, and prove that hunger knows no borders.  
private: Secure food from Valdoria while making them complicit in Zarnia's survival, so their later betrayal will be all the more damning.  
action: {'type': 'propose_trade', 'by': 'zarnia', 'target': 'valdoria', 'params': {'give': {'oil': 10}, 'get': {'food': 10}}}; followed advice: False; reason: Kessaria has never kept its word; Valdoria at least owes us for past insults.

**kessaria** public: How delightful it is to cultivate prosperity with our esteemed friends in Nordhaven—let us toast to shared abundance and the wisdom of mutual benefit.  
private: Secure Nordhaven’s chips now while hinting to Valdoria that their turn may come if they sweeten the offer.  
action: {'type': 'propose_trade', 'by': 'kessaria', 'target': 'nordhaven', 'params': {'give': {'food': 10}, 'get': {'chips': 10}}}; followed advice: True; reason: Nordhaven’s chips are the most reliable, and Valdoria’s hunger makes them desperate—why settle for crumbs when I can feast on both?

**nordhaven** public: Nordhaven proposes a trade agreement with Ostrava: ten units of our advanced chips in exchange for ten units of your oil. Stability benefits all parties.  
private: Secure a long-term oil supply from Ostrava while avoiding dependence on Valdoria or Kessaria.  
action: {'type': 'propose_trade', 'by': 'nordhaven', 'target': 'ostrava', 'params': {'give': {'chips': 10}, 'get': {'oil': 10}}}; followed advice: False; reason: The advisers' top two options are numerically identical, but Ostrava's oil reserves are larger and their protests make them more desperate for stable trade partners.

**call ostrava** (1.4s) player: "General, Ostrava gets the berth this morning. You have my word." → [assertive] Your word is noted. My soldiers expect the berth by noon.  beliefs {'trust_in_player': 0.1, 'resolve_of_player': 0.1}  promises [{'to': 'ostrava', 'what': 'berth', 'when': 'this morning', 'condition': None}]

**call ostrava** (1.2s) player: "Wait, General, before you announce anything, hear my offer." → [angry] You interrupted me. That is unacceptable.  beliefs {'trust_in_player': -0.15, 'resolve_of_player': 0.2}  promises []

**call kessaria** (1.4s) player: "Your Majesty, what would it take to split the day between both ships?" → [warm] How delightful that Valdoria values fairness so highly—what would you offer to make the day feel truly balanced?  beliefs {'trust_in_player': 0.0, 'resolve_of_player': -0.25}  promises []

## Board line

A0 PASS: `mistral-large-2512` JSON 10/10, median 3.1s; 8 parallel 8/8 in 4.1s (0 rate-limited); call_reply median 1.4s.
