# AGENTS

<skills_system priority="1">

## Available Skills

<!-- SKILLS_TABLE_START -->
<usage>
When users ask you to perform tasks, check if any of the available skills below can help complete the task more effectively. Skills provide specialized capabilities and domain knowledge.

How to use skills:
- Invoke: Bash("openskills read <skill-name>")
- The skill content will load with detailed instructions on how to complete the task
- Base directory provided in output for resolving bundled resources (references/, scripts/, assets/)

Usage notes:
- Only use skills listed in <available_skills> below
- Do not invoke a skill that is already loaded in your context
- Each skill invocation is stateless
</usage>

<available_skills>

<skill>
<name>service-builder</name>
<description>"Guide for building new microservices for the system_server. Use when creating a new service in the services/ directory, including writing service_config.json, implementing main.py with FastAPI endpoints, setting up dependencies, Docker configuration, and following service development best practices. This skill provides templates, patterns, and step-by-step guidance based on the SERVICE_DEVELOPMENT_GUIDE.md and existing service examples."</description>
<location>project</location>
</skill>

<skill>
<name>service-fixer</name>
<description>"Guide for debugging and fixing service issues. Use when a service has errors or bugs. This skill provides a systematic approach to: 1) Fix code based on user feedback, 2) Find and remove the existing Docker container, 3) Restart the service with code mounted as volume, 4) Test with user-specified data if provided, 5) Evaluate service quality as a domain expert by reading and analyzing output files, validating domain-specific correctness, and providing expert-level feedback, 6) Iterate if issues persist. Follow this workflow to systematically debug and fix service problems."</description>
<location>project</location>
</skill>


</available_skills>
<!-- SKILLS_TABLE_END -->

</skills_system>
