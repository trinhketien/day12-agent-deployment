"""
Mock LLM — dùng chung cho tất cả ví dụ.
Không cần API key thật. Trả lời giả lập để focus vào deployment concept.
"""
import time
import random


MOCK_RESPONSES = {
    "default": [
        "Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.",
        "Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.",
        "Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận và xử lý.",
    ],
    "docker": [
        "Docker là nền tảng containerization cho phép đóng gói app + dependencies vào một container. "
        "Build once, run anywhere! Container nhẹ hơn VM và khởi động nhanh hơn nhiều."
    ],
    "deploy": [
        "Deployment là quá trình đưa code từ máy bạn lên server để người khác dùng được. "
        "Sử dụng Railway hoặc Render để deploy nhanh chỉ trong 5 phút!"
    ],
    "health": [
        "Agent đang hoạt động bình thường. All systems operational. "
        "Health check endpoint trả về 200 OK."
    ],
    "kubernetes": [
        "Kubernetes (K8s) là hệ thống orchestration container mã nguồn mở. "
        "Nó tự động deploy, scale và quản lý containerized applications."
    ],
    "redis": [
        "Redis là in-memory data store cực nhanh. Dùng cho cache, session storage, "
        "rate limiting, và pub/sub messaging. Hoàn hảo cho stateless design!"
    ],
    "scale": [
        "Horizontal scaling = thêm nhiều instances. Vertical scaling = nâng cấp phần cứng. "
        "Với stateless design + Redis, bạn có thể scale horizontally vô hạn!"
    ],
    "security": [
        "Bảo mật API cần 3 lớp: (1) Authentication - ai được dùng, "
        "(2) Rate Limiting - giới hạn tần suất, (3) Cost Guard - giới hạn chi phí."
    ],
    "12factor": [
        "12-Factor App là bộ best practices cho cloud-native apps: "
        "config từ env vars, stateless processes, disposable containers, "
        "dev/prod parity, và structured logging."
    ],
}


def ask(question: str, delay: float = 0.1) -> str:
    """Mock LLM call với delay giả lập latency thật."""
    time.sleep(delay + random.uniform(0, 0.05))  # simulate API latency

    question_lower = question.lower()
    for keyword, responses in MOCK_RESPONSES.items():
        if keyword in question_lower:
            return random.choice(responses)

    return random.choice(MOCK_RESPONSES["default"])


def ask_stream(question: str):
    """Mock streaming response — yield từng token."""
    response = ask(question)
    words = response.split()
    for word in words:
        time.sleep(0.05)
        yield word + " "
