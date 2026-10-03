import os
from pathlib import Path

import streamlit as st

from agent import fake_model, run_agent
from brain import ask_model

st.set_page_config(page_title="Repo Surgeon", page_icon="🩺", layout="wide")

st.title("🩺 Repo Surgeon")
st.caption("An autonomous agent that repairs broken code until the tests pass.")

has_key = bool(os.environ.get("NEBIUS_API_KEY") and os.environ.get("NEBIUS_MODEL"))

with st.sidebar:
    st.header("Settings")
    use_fake = st.checkbox("Use pretend model (testing only)", value=not has_key)
    if use_fake:
        st.warning("Pretend model: nothing is sent to Nebius.")
    elif has_key:
        st.success("Using Nebius Token Factory: " + os.environ["NEBIUS_MODEL"])
    else:
        st.error("No key set yet.")
    max_attempts = st.slider("Max attempts", 1, 8, 5)

project = st.selectbox(
    "Project to repair",
    ["demo_project", "demo_orders"],
    format_func=lambda name: {
        "demo_project": "Shopping cart (1 bug, 1 file)",
        "demo_orders": "Order totals (2 bugs, 2 files)",
    }[name],
)


def show_count(placeholder, value, previous=None):
    delta = None if previous is None else value - previous
    placeholder.metric("Failing tests", value, delta=delta, delta_color="inverse")


if st.button("Repair it", type="primary"):
    if not Path(project).is_dir():
        st.error(f"Folder not found: {project}")
        st.stop()

    model_fn = fake_model if use_fake else ask_model
    counter = st.empty()
    count = None

    with st.spinner("Repo Surgeon is working..."):
        for event in run_agent(project, model_fn=model_fn, max_attempts=max_attempts):
            kind = event["type"]

            if kind == "start":
                count = event["result"]["failed"]
                show_count(counter, count)
                with st.expander("Starting test output"):
                    st.code(event["result"]["output"])

            elif kind == "attempt":
                reply = event["reply"]
                confidence = reply.get("confidence", 0)
                if not isinstance(confidence, (int, float)):
                    confidence = 0
                with st.container(border=True):
                    st.subheader(f"Attempt {event['attempt']}")
                    st.write("**Diagnosis:** " + str(reply.get("diagnosis", "")))
                    st.write("**Fix tried:** " + str(reply.get("hypothesis", "")))
                    st.progress(
                        min(max(float(confidence), 0.0), 1.0),
                        text=f"Model confidence: {confidence:.0%}",
                    )
                    for name, diff in event["diffs"].items():
                        st.code(diff, language="diff")
                    if event["reverted"]:
                        st.warning(
                            f"Made things worse ({event['failed_before']} -> "
                            f"{event['failed_after']} failing). Fix undone."
                        )
                    else:
                        st.success(
                            f"Kept: {event['failed_before']} -> "
                            f"{event['failed_after']} failing tests."
                        )
                new_count = event["failed_before"] if event["reverted"] else event["failed_after"]
                show_count(counter, new_count, count)
                count = new_count

            elif kind == "rejected":
                st.warning(f"Attempt {event['attempt']} was rejected: {event['message']}")

            elif kind == "success":
                st.success("All tests pass. Repair complete.")
                st.balloons()

            elif kind == "gave_up":
                st.warning("The agent gave up: " + event["reason"])

            elif kind == "out_of_attempts":
                st.error("Out of attempts. Some tests still fail.")

            elif kind == "error":
                st.error("Something went wrong: " + event["message"])