import { ChatWindow } from "@/components/chat/ChatWindow";

export default async function ConversationPage({
  params,
}: {
  params: Promise<{ conversationId: string }>;
}) {
  const { conversationId } = await params;
  return <ChatWindow key={conversationId} conversationId={conversationId} />;
}
