"""Streamlit entry point: run from the project root."""

import streamlit as st


def main() -> None:
    st.set_page_config(page_title="CampusAgent", page_icon="🎓")
    st.title("🎓 CampusAgent")
    st.write("面向 CampusTrain 的独立智能课程客服 Agent。")
    st.info("当前阶段：Python 工程初始化。")
    st.markdown(
        "后续将支持课程咨询、报名查询、学习进度查询、取消报名确认、"
        "规则检索与多轮对话。"
    )
    st.caption("业务功能尚未接入；当前页面无需模型密钥或 CampusTrain 在线。")


if __name__ == "__main__":
    main()
