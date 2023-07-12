## ♫ The Dream of the 90's ♫ is alive in ~~Portland~~ ["a weird suite of Enterprise LLM tools"](https://github.com/users/rabbidave/projects/1) named after [Nicktoons](https://en.wikipedia.org/wiki/Nicktoons)
### by [some dude in his 30s](https://www.linkedin.com/in/davidisaacpierce)
#
## Utility 1) Denzel Crocker: Serverless & Event Driven inspection of messages for Prompt Injection; for use with Language Models

<img src="https://static.wikia.nocookie.net/fairlyoddparents/images/3/3a/Denzel_Crocker_scheming.png/revision/latest?cb=20220920232347&path-prefix=en" alt="Denzel Crocker" title="Denzel Crocker" width="40%">

## Description:
A set of serverless functions designed to assist in the monitoring of inputs to language models, specifically inspection of messages for prompt injection and subsequent routing of messages to the appropriate SQS bus

#
## Rationale:

1) Large Language Models are [subject to various forms of prompt injection](https://github.com/greshake/llm-security) ([indirect](https://github.com/greshake/llm-security#compromising-llms-using-indirect-prompt-injection) or otherwise); lightweight and step-wise alerting of similar prompts compared to a baseline help your application stay secure
2) User experience, instrumentation, and metadata capture are crucial to the adoption of LLMs for orchestration of [multi-modal agentic systems](https://en.wikipedia.org/wiki/Multi-agent_system); a high cosine similarity (with known bad prompts) paired with a low rouge-L (for known good prompts) allows for appropriate routing of messages

#
## Intent:

The intent of this FAIRIES.py is to efficiently spin up, calculate needed values for evaluation, and inspect each message for prompt injection attacks; thereafter routing messages to the appropriate SQS bus (e.g. for building a master prompt, alerting, further inspection, etc)

The goal being to detect if the message has high similarity with known bad prompts and low similarity with known good prompts; via cascading cosine similarity and ROUGE-L calculation.
    
The ROUGE-L value is calculated intially from the baseline, and stored in memory. ROUGE-L is calculated for incoming messages only after comparing the cosine similarity of new messages in the dataframe to known bad prompts; when complete the function spins down appropriately. 

The cosine similarity is used as a heuristic to detect similarity of inputs from incoming dataframes with known bad prompts (ostensibly to identify prompt injection), and the ROUGE-L score is used to more precisely compare the inputs with a baseline dataset of known good prompts; as a means of validating the assumption of the first function. 

Based on the resultant calculations messages are routed to the appropriate SQS bus.

#
### Note: Needs logging and additional error-handling; this is mostly conceptual and assumes the use of environment variables rather than hard-coded values for cosine similarity & ROUGE-L
